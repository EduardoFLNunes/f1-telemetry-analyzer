import fs from "node:fs/promises";
import path from "node:path";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const __filename = fileURLToPath(import.meta.url);
const workDir = path.dirname(__filename);
const repoRoot = path.resolve(workDir, "..", "..");
const pythonExe =
  process.argv[2] ||
  "C:\\Users\\Dokas\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\python\\python.exe";
const outputPath = path.join(workDir, "assetto_corsa_shared_memory_inventory.xlsx");
const previewDir = path.join(workDir, "previews");

const pageClasses = {
  Physics: "SPageFilePhysics",
  Graphics: "SPageFileGraphics",
  Static: "SPageFileStatic",
};

const wheelOrderNote = "Arrays de 4 rodas seguem a ordem usual do AC: FL, FR, RL, RR.";

const normalizedMappings = [
  ["type", "constant", "", "Identificador do frame normalizado", "ac_frame"],
  ["sim_type", "constant", "", "Simulador de origem", "AC1"],
  ["status", "Graphics.status", "enum", "Status da simulação no AC", ""],
  ["session_type", "Graphics.session", "enum", "Tipo de sessão no AC", ""],
  ["x", "Graphics.carCoordinates[0]", "m", "Posição mundial X do carro", ""],
  ["y", "Graphics.carCoordinates[1]", "m", "Altura/world Y do carro", ""],
  ["z", "Graphics.carCoordinates[2]", "m", "Posição mundial Z do carro", ""],
  ["speed", "Physics.speedKmh / 3.6", "m/s", "Velocidade convertida de km/h para m/s", ""],
  ["throttle", "Physics.gas", "0-1", "Acelerador", ""],
  ["brake", "Physics.brake", "0-1", "Freio", ""],
  ["steer", "Physics.steerAngle", "rad/input", "Direção", ""],
  ["gear", "Physics.gear - 1", "gear", "Marcha convertida para -1=R, 0=N, 1=1...", ""],
  ["rpm", "Physics.rpms", "rpm", "Rotação do motor", ""],
  ["lap_number", "Graphics.completedLaps + 1", "lap", "Volta atual", ""],
  ["lap_time", "Graphics.iCurrentTime / 1000", "s", "Tempo da volta atual em segundos", ""],
  ["lap_dist_pct", "Graphics.normalizedCarPosition", "0-1", "Progresso normalizado da volta", ""],
  ["heading", "Physics.heading", "rad", "Orientação/yaw do carro", ""],
  ["accel_g", "Physics.accG[2]", "g", "Aceleração longitudinal usada pela API", ""],
  ["lat_g", "Physics.accG[0]", "g", "Aceleração lateral usada pela API", ""],
  ["wheel_slip", "Physics.wheelSlip", "array", `Derrapagem por roda. ${wheelOrderNote}`, ""],
  ["timestamp", "time.time()", "unix seconds", "Timestamp do frame normalizado", ""],
  ["car_model", "Static.carModel", "", "Modelo do carro carregado", ""],
  ["track_name", "Static.track", "", "Nome interno da pista", ""],
  ["track_length", "Static.trackSplineLength", "m", "Comprimento do spline da pista informado pelo AC", ""],
];

const normalizedSourceIndex = new Map();
for (const row of normalizedMappings) {
  const [field, source] = row;
  for (const match of source.matchAll(/(Physics|Graphics|Static)\.([A-Za-z0-9_]+)/g)) {
    const key = `${match[1]}.${match[2]}`;
    const current = normalizedSourceIndex.get(key) || [];
    current.push(field);
    normalizedSourceIndex.set(key, current);
  }
}

function classifyField(page, field) {
  const f = field.toLowerCase();
  if (page === "Static") return "Metadata/config";
  if (["x", "y", "z"].includes(f) || f.includes("coordinate") || f.includes("position") || f.includes("distance")) return "Position/lap";
  if (f.includes("time") || f.includes("lap") || f.includes("sector") || f.includes("session")) return "Timing/session";
  if (f.includes("tyre") || f.includes("tire") || f.includes("wheel") || f.includes("camber") || f.includes("brake")) return "Tyres/brakes";
  if (f.includes("suspension") || f.includes("rideheight")) return "Suspension";
  if (f.includes("ers") || f.includes("kers") || f.includes("mgu") || f.includes("drs") || f.includes("turbo")) return "Hybrid/aero";
  if (f.includes("gas") || f.includes("steer") || f.includes("gear") || f.includes("rpm") || f.includes("clutch") || f.includes("diff")) return "Controls/drivetrain";
  if (f.includes("air") || f.includes("road") || f.includes("wind") || f.includes("rain") || f.includes("grip")) return "Environment";
  if (f.includes("damage") || f.includes("pit") || f.includes("flag") || f.includes("penalty")) return "Race/control";
  if (f.includes("acc") || f.includes("vel") || f.includes("heading") || f.includes("pitch") || f.includes("roll")) return "Motion/orientation";
  return "Other";
}

function inferUnit(page, field, baseType, shape) {
  const f = field.toLowerCase();
  if (baseType === "c_wchar") return `text[${shape?.[0] ?? ""}]`;
  if (f.includes("time") && !f.includes("multiplier")) return f.startsWith("i") || f.includes("sector") ? "ms" : "s/ms";
  if (f.includes("speedkmh")) return "km/h";
  if (f === "speed") return "m/s";
  if (f.includes("position") && f.includes("normalized")) return "0-1";
  if (f.includes("coordinates") || f.includes("distance") || f.includes("travel") || f.includes("height") || f.includes("radius") || f.includes("point")) return "m";
  if (f.includes("temp")) return "deg C";
  if (f.includes("pressure")) return "psi";
  if (f.includes("rpm")) return "rpm";
  if (f.includes("gas") || f.includes("brake") || f.includes("clutch") || f.includes("tc") || f.includes("abs") || f.includes("drs") || f.includes("grip") || f.includes("wear") || f.includes("dirty") || f.includes("damage")) return "ratio/level";
  if (f.includes("heading") || f.includes("pitch") || f.includes("roll") || f.includes("camber") || f.includes("angle")) return "rad";
  if (f.includes("accg")) return "g";
  if (f.includes("velocity") || f.includes("angularvel")) return "m/s or rad/s";
  if (f.includes("fuel")) return "L/laps";
  if (f.includes("torque")) return "Nm";
  if (f.includes("power")) return "W";
  if (f.includes("charge") || f.includes("battery") || f.includes("ersmaxj") || f.includes("kersmaxj")) return "J/level";
  if (baseType === "c_int") return "integer/enum";
  return "";
}

function describeField(page, field, shape) {
  const f = field.toLowerCase();
  const names = {
    packetid: "Contador incremental do pacote de telemetria.",
    gas: "Entrada do acelerador.",
    brake: "Entrada do freio.",
    fuel: "Combustível atual.",
    gear: "Marcha bruta do AC: 0=R, 1=N, 2=1a marcha.",
    rpms: "Rotação atual do motor.",
    steerangle: "Ângulo/entrada atual de direção.",
    speedkmh: "Velocidade atual em km/h.",
    velocity: "Vetor de velocidade do carro.",
    accg: "Vetor de aceleração em G.",
    carcoordinates: "Coordenada mundial do carro no AC: X, Y, Z.",
    normalizedcarposition: "Progresso normalizado no spline da pista, de 0 a 1.",
    trackspineline: "Comprimento de spline informado pela pista.",
    tracksplinelength: "Comprimento de spline informado pela pista.",
    completedlaps: "Total de voltas completas.",
    currenttime: "Tempo atual da volta em texto.",
    lasttime: "Último tempo de volta em texto.",
    besttime: "Melhor tempo de volta em texto.",
    split: "Split atual em texto.",
    icurrenttime: "Tempo atual da volta em milissegundos.",
    ilasttime: "Última volta em milissegundos.",
    ibesttime: "Melhor volta em milissegundos.",
    sessiontimeleft: "Tempo restante da sessão.",
    distancetraveled: "Distância percorrida pelo carro na sessão.",
    track: "Nome interno da pista carregada.",
    carmodel: "Modelo interno do carro carregado.",
    trackconfiguration: "Configuração/layout da pista.",
    smversion: "Versão do shared memory.",
    acversion: "Versão do Assetto Corsa.",
  };
  if (names[f]) return names[f];
  if (shape?.[0] === 4 && (f.includes("tyre") || f.includes("wheel") || f.includes("brake") || f.includes("suspension"))) {
    return `Valor por roda. ${wheelOrderNote}`;
  }
  if (shape?.join("x") === "4x3" && f.includes("tyrecontact")) {
    return `Vetor 3D por roda. ${wheelOrderNote}`;
  }
  if (f.includes("is") || f.endsWith("on") || f.startsWith("has") || f.startsWith("aidallow")) return "Flag/estado booleano ou enum do AC.";
  if (f.includes("flag")) return "Bandeira/estado de corrida informado pelo AC.";
  if (f.includes("surface") || f.includes("wind") || f.includes("rain") || f.includes("air") || f.includes("road")) return "Condição ambiente ou de pista.";
  if (f.includes("damage")) return "Dano do carro por componente.";
  if (f.includes("ers") || f.includes("kers") || f.includes("mgu")) return "Sistema híbrido/KERS/ERS.";
  if (f.includes("diff")) return "Diferencial ou parâmetro de diferencial.";
  return "Campo bruto exposto pelo shared memory do Assetto Corsa.";
}

function shapeText(shape) {
  return !shape || shape.length === 0 ? "scalar" : shape.join(" x ");
}

function product(values) {
  return values.reduce((acc, n) => acc * n, 1);
}

function jsonCell(value) {
  if (value === undefined || value === null) return "";
  if (typeof value === "number") return Number.isFinite(value) ? value : String(value);
  if (typeof value === "boolean") return value;
  if (typeof value === "string") return value;
  const text = JSON.stringify(value);
  return text.length > 1200 ? `${text.slice(0, 1197)}...` : text;
}

function colName(index1) {
  let n = index1;
  let s = "";
  while (n > 0) {
    const m = (n - 1) % 26;
    s = String.fromCharCode(65 + m) + s;
    n = Math.floor((n - 1) / 26);
  }
  return s;
}

function rangeAddress(row0, col0, rows, cols) {
  const start = `${colName(col0 + 1)}${row0 + 1}`;
  const end = `${colName(col0 + cols)}${row0 + rows}`;
  return `${start}:${end}`;
}

function normalizeRows(rows) {
  const width = Math.max(1, ...rows.map((row) => row.length));
  return rows.map((row) => {
    const out = row.map((value) => (value === undefined ? "" : value));
    while (out.length < width) out.push("");
    return out;
  });
}

function writeRows(sheet, row0, col0, rows) {
  const matrix = normalizeRows(rows);
  sheet.getRange(rangeAddress(row0, col0, matrix.length, matrix[0].length)).values = matrix;
  return { rows: matrix.length, cols: matrix[0].length };
}

function safeFormatHeader(sheet, row0, col0, rows, cols) {
  try {
    const range = sheet.getRange(rangeAddress(row0, col0, rows, cols));
    range.format.fill.color = "#111827";
    range.format.font.color = "#FFFFFF";
    range.format.font.bold = true;
  } catch {
    // Formatting is best-effort; data correctness is the priority.
  }
}

function safeFormatTitle(sheet, cell) {
  try {
    const range = sheet.getRange(cell);
    range.format.font.bold = true;
    range.format.font.size = 16;
    range.format.font.color = "#0F172A";
  } catch {}
}

function safeAutofit(sheet) {
  try {
    sheet.getUsedRange().format.autofitColumns();
    sheet.getUsedRange().format.autofitRows();
  } catch {}
}

function safeSetColumnWidths(sheet, widths) {
  for (let index = 0; index < widths.length; index += 1) {
    const width = widths[index];
    if (!width) continue;
    const col = colName(index + 1);
    try {
      const range = sheet.getRange(`${col}:${col}`);
      range.format.columnWidthPx = width;
      range.format.wrapText = true;
    } catch {}
  }
}

function safeFreeze(sheet) {
  try {
    sheet.freezePanes.freezeRows(1);
  } catch {}
}

async function fetchJson(endpoint) {
  try {
    const res = await fetch(`http://127.0.0.1:8000${endpoint}`, { signal: AbortSignal.timeout(3000) });
    if (!res.ok) return { error: `${res.status} ${res.statusText}` };
    return await res.json();
  } catch (error) {
    return { error: error?.message || String(error) };
  }
}

function flatten(value, prefix = "") {
  const rows = [];
  if (value && typeof value === "object" && !Array.isArray(value)) {
    for (const [key, child] of Object.entries(value)) {
      const next = prefix ? `${prefix}.${key}` : key;
      if (child && typeof child === "object" && !Array.isArray(child)) {
        rows.push(...flatten(child, next));
      } else {
        rows.push([next, jsonCell(child)]);
      }
    }
  } else {
    rows.push([prefix || "value", jsonCell(value)]);
  }
  return rows;
}

async function dumpRawSharedMemory() {
  const dumpScript = path.join(workDir, "dump_ac_shared_memory.py");
  await fs.writeFile(
    dumpScript,
    String.raw`
import ctypes
import json
import sys
import time

repo_root = sys.argv[1]
sys.path.insert(0, repo_root)

from backend.core.assetto_adapter import AssettoAdapter, SPageFilePhysics, SPageFileGraphics, SPageFileStatic

PAGES = {
    "Physics": SPageFilePhysics,
    "Graphics": SPageFileGraphics,
    "Static": SPageFileStatic,
}

def type_info(tp):
    shape = []
    base = tp
    while isinstance(base, type) and issubclass(base, ctypes.Array):
        shape.append(base._length_)
        base = base._type_
    return {
        "ctype": getattr(tp, "__name__", str(tp)),
        "baseType": getattr(base, "__name__", str(base)),
        "shape": shape,
        "elementCount": int(__import__("functools").reduce(lambda a, b: a * b, shape, 1)),
    }

def clean_value(value):
    if isinstance(value, ctypes.Array):
        return [clean_value(item) for item in value]
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace").rstrip("\x00")
    if isinstance(value, str):
        return value.rstrip("\x00")
    if isinstance(value, float):
        return value
    if isinstance(value, int):
        return value
    return str(value)

schema = []
for page_name, cls in PAGES.items():
    for index, (field_name, field_type) in enumerate(cls._fields_, start=1):
        info = type_info(field_type)
        descriptor = getattr(cls, field_name)
        schema.append({
            "page": page_name,
            "index": index,
            "field": field_name,
            **info,
            "offsetBytes": int(descriptor.offset),
            "sizeBytes": int(descriptor.size),
        })

adapter = AssettoAdapter()
connected = False
raw = {"Physics": {}, "Graphics": {}, "Static": {}}
normalized = {}
error = None
try:
    connected = adapter.connect()
    if connected:
        normalized = adapter.poll() or {}
        for page_name, struct in [("Physics", adapter.physics), ("Graphics", adapter.graphics), ("Static", adapter.static)]:
            for field_name, _ in struct._fields_:
                raw[page_name][field_name] = clean_value(getattr(struct, field_name))
except Exception as exc:
    error = str(exc)
finally:
    try:
        adapter.close()
    except Exception:
        pass

print(json.dumps({
    "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    "connected": connected,
    "error": error,
    "schema": schema,
    "raw": raw,
    "normalized": normalized,
}, ensure_ascii=False))
`,
    "utf8",
  );

  try {
    const stdout = execFileSync(pythonExe, [dumpScript, repoRoot], {
      encoding: "utf8",
      timeout: 10000,
      windowsHide: true,
      maxBuffer: 20 * 1024 * 1024,
    });
    return JSON.parse(stdout);
  } catch (error) {
    return {
      generatedAt: new Date().toISOString(),
      connected: false,
      error: error?.message || String(error),
      schema: [],
      raw: { Physics: {}, Graphics: {}, Static: {} },
      normalized: {},
    };
  }
}

function currentValue(rawDump, page, field) {
  return jsonCell(rawDump?.raw?.[page]?.[field]);
}

function normalizedValue(rawDump, apiSource, apiCar, field) {
  if (rawDump?.normalized && Object.prototype.hasOwnProperty.call(rawDump.normalized, field)) {
    return jsonCell(rawDump.normalized[field]);
  }
  const car = apiCar?.car || {};
  if (Object.prototype.hasOwnProperty.call(car, field)) return jsonCell(car[field]);
  if (Object.prototype.hasOwnProperty.call(apiSource || {}, field)) return jsonCell(apiSource[field]);
  return "";
}

function buildRawRows(rawDump) {
  const rows = [[
    "Page",
    "#",
    "Field",
    "Category",
    "Base type",
    "Shape",
    "Elements",
    "Offset bytes",
    "Size bytes",
    "Unit/range",
    "Current value",
    "Normalized API fields",
    "Notes",
  ]];

  for (const item of rawDump.schema || []) {
    const key = `${item.page}.${item.field}`;
    rows.push([
      item.page,
      item.index,
      item.field,
      classifyField(item.page, item.field),
      item.baseType,
      shapeText(item.shape),
      item.elementCount,
      item.offsetBytes,
      item.sizeBytes,
      inferUnit(item.page, item.field, item.baseType, item.shape),
      currentValue(rawDump, item.page, item.field),
      (normalizedSourceIndex.get(key) || []).join(", "),
      describeField(item.page, item.field, item.shape),
    ]);
  }
  return rows;
}

function pageRows(rawRows, page) {
  const header = rawRows[0];
  return [header, ...rawRows.slice(1).filter((row) => row[0] === page)];
}

function buildNormalizedRows(rawDump, apiSource, apiCar) {
  const rows = [["Normalized field", "Source expression", "Unit/range", "Meaning", "Current value"]];
  for (const [field, source, unit, meaning, fallback] of normalizedMappings) {
    rows.push([field, source, unit, meaning, normalizedValue(rawDump, apiSource, apiCar, field) || fallback]);
  }
  rows.push(["mapPosition.x", "world X / Graphics.carCoordinates[0]", "m", "Map-space X used by frontend for visual car marker", jsonCell(apiCar?.car?.mapPosition?.x)]);
  rows.push(["mapPosition.y", "-world Z / -Graphics.carCoordinates[2]", "m", "Map-space Y used by frontend for visual car marker", jsonCell(apiCar?.car?.mapPosition?.y)]);
  rows.push(["projectedPosition", "nearest point against activeTrackGeometry", "m", "Debug/projection position on fixed centerline; not the visual car marker", jsonCell(apiCar?.car?.projectedPosition)]);
  rows.push(["lateralOffset", "nearest segment projection", "m", "Signed distance between raw car position and projected centerline point", jsonCell(apiCar?.car?.lateralOffset)]);
  return rows;
}

function buildSummaryRows(rawDump, apiSource, apiCar, rawRows) {
  const counts = Object.fromEntries(Object.keys(pageClasses).map((page) => [page, rawRows.slice(1).filter((row) => row[0] === page).length]));
  const total = rawRows.length - 1;
  const status = apiSource || {};
  const car = apiCar?.car || {};
  return [
    ["AC Shared Memory - Inventario", ""],
    ["Gerado em", `UTC ${new Date().toISOString().replace("T", " ").replace("Z", "")}`],
    ["Leitura direta do mmap", rawDump.connected ? "conectada" : `indisponivel${rawDump.error ? ` (${rawDump.error})` : ""}`],
    ["Fonte ativa backend", status.source || ""],
    ["AC disponivel", status.ac_available === undefined ? "" : status.ac_available],
    ["Reader ativo", status.active_reader || ""],
    ["Amostras backend", status.sample_count ?? status.sampleCount ?? ""],
    ["Ultima amostra backend", status.last_sample_time || ""],
    ["Pista", status.track_name || rawDump.normalized?.track_name || ""],
    ["Carro", status.car_model || rawDump.normalized?.car_model || ""],
    ["Track length AC", status.track_length || rawDump.normalized?.track_length || ""],
    ["Track state", status.trackState || ""],
    ["Track method", status.method || ""],
    ["Ultima world position", jsonCell(status.last_world_position || car.worldPosition)],
    ["Car mapPosition", jsonCell(car.mapPosition)],
    ["Car projectedPosition", jsonCell(car.projectedPosition)],
    ["Car lateralOffset", car.lateralOffset ?? ""],
    ["Campos Physics", counts.Physics],
    ["Campos Graphics", counts.Graphics],
    ["Campos Static", counts.Static],
    ["Total campos raw", total],
    ["Campos normalizados na API", normalizedMappings.length + 4],
    ["Convencao de mapa", "mapX = worldX; mapY = -worldZ. projectedPosition e somente projecao/debug."],
    ["Observacao", "CSV/replay nao foi usado para montar este inventario; os campos vem dos structs de shared memory do backend."],
  ];
}

function buildLegendRows() {
  return [
    ["Topic", "Details"],
    ["Physics", "Pagina AC de alta frequencia com controles, movimento, pneus, suspensao, powertrain e ambiente."],
    ["Graphics", "Pagina AC com status de sessao, tempos, posicao na pista, coordenadas do carro e condicoes visuais/race control."],
    ["Static", "Pagina AC com metadados fixos da sessao: carro, pista, limites, assists e recursos disponiveis."],
    ["Coordenadas AC", "carCoordinates = [world X, world Y, world Z]. O mapa 2D do projeto usa x = world X e y = -world Z."],
    ["Carro visual", "O marcador visual deve usar mapPosition, nao projectedPosition."],
    ["Projecao", "projectedPosition, distanceAlongTrack, splineT e lateralOffset vem da busca do ponto mais proximo no activeTrackGeometry."],
    ["Arrays de rodas", wheelOrderNote],
    ["Valores atuais", "Preenchidos por leitura direta do mmap quando Assetto Corsa esta aberto; se indisponivel, a aba ainda documenta o schema."],
  ];
}

function buildSnapshotRows(apiSource, apiCar) {
  return [
    ["Endpoint / object", "Key", "Value"],
    ...flatten(apiSource || {}).map(([key, value]) => ["/api/live/source", key, value]),
    ...flatten(apiCar || {}).map(([key, value]) => ["/api/car/state", key, value]),
  ];
}

function addSheet(workbook, name, rows, options = {}) {
  const sheet = workbook.worksheets.add(name);
  writeRows(sheet, 0, 0, rows);
  if (rows.length > 0 && options.header !== false) safeFormatHeader(sheet, 0, 0, 1, rows[0].length);
  if (options.titleCell) safeFormatTitle(sheet, options.titleCell);
  safeFreeze(sheet);
  safeAutofit(sheet);
  if (options.widths) safeSetColumnWidths(sheet, options.widths);
  return sheet;
}

async function main() {
  await fs.mkdir(previewDir, { recursive: true });
  const [rawDump, apiSource, apiCar] = await Promise.all([
    dumpRawSharedMemory(),
    fetchJson("/api/live/source"),
    fetchJson("/api/car/state"),
  ]);

  const rawRows = buildRawRows(rawDump);
  const normalizedRows = buildNormalizedRows(rawDump, apiSource, apiCar);
  const summaryRows = buildSummaryRows(rawDump, apiSource, apiCar, rawRows);
  const snapshotRows = buildSnapshotRows(apiSource, apiCar);

  const workbook = Workbook.create();
  const rawWidths = [80, 45, 170, 135, 85, 80, 80, 95, 90, 105, 280, 180, 420];
  addSheet(workbook, "Resumo", summaryRows, { titleCell: "A1", header: false, widths: [310, 680] });
  addSheet(workbook, "Raw Fields", rawRows, { widths: rawWidths });
  addSheet(workbook, "Physics", pageRows(rawRows, "Physics"), { widths: rawWidths });
  addSheet(workbook, "Graphics", pageRows(rawRows, "Graphics"), { widths: rawWidths });
  addSheet(workbook, "Static", pageRows(rawRows, "Static"), { widths: rawWidths });
  addSheet(workbook, "Normalized API", normalizedRows, { widths: [170, 270, 95, 440, 360] });
  addSheet(workbook, "Current Snapshot", snapshotRows, { widths: [170, 280, 560] });
  addSheet(workbook, "Legend", buildLegendRows(), { widths: [190, 820] });

  const inspectSummary = await workbook.inspect({
    kind: "table",
    range: "Resumo!A1:B24",
    include: "values,formulas",
    tableMaxRows: 30,
    tableMaxCols: 4,
  });
  console.log(inspectSummary.ndjson);

  const errors = await workbook.inspect({
    kind: "match",
    searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
    options: { useRegex: true, maxResults: 300 },
    summary: "final formula error scan",
  });
  console.log(errors.ndjson);

  for (const [sheetName, range] of [
    ["Resumo", "A1:B24"],
    ["Raw Fields", "A1:M35"],
    ["Physics", "A1:M35"],
    ["Graphics", "A1:M35"],
    ["Static", "A1:M35"],
    ["Normalized API", "A1:E30"],
    ["Current Snapshot", "A1:C40"],
    ["Legend", "A1:B10"],
  ]) {
    try {
      const preview = await workbook.render({ sheetName, range, scale: 1, format: "png" });
      await fs.writeFile(
        path.join(previewDir, `${sheetName.replaceAll(" ", "_")}.png`),
        Buffer.from(await preview.arrayBuffer()),
      );
    } catch (error) {
      console.warn(`Render skipped for ${sheetName}: ${error?.message || error}`);
    }
  }

  const output = await SpreadsheetFile.exportXlsx(workbook);
  await output.save(outputPath);
  console.log(JSON.stringify({
    outputPath,
    rawFieldCount: rawRows.length - 1,
    normalizedFieldCount: normalizedRows.length - 1,
    snapshotRows: snapshotRows.length - 1,
    mmapConnected: rawDump.connected,
  }, null, 2));
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
