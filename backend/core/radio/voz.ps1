# A voz do rádio (pedido 31, Parte B.3): o texto vira um WAV com uma voz pt-BR do Windows.
# Nada é instalado: as vozes OneCore vêm do Windows.Media.SpeechSynthesis e a SAPI 5 do System.Speech.
#
# Uso: powershell -NoProfile -ExecutionPolicy Bypass -File voz.ps1 -Texto <arquivo .txt em UTF-8> -Saida <arquivo .wav> -Voz <OneCore:Daniel|OneCore:Maria|SAPI:Maria|listar>
param(
  [string]$Texto,
  [string]$Saida,
  [string]$Voz = 'OneCore:Daniel',
  [double]$Velocidade = 1.0
)
$ErrorActionPreference = 'Stop'

if ($Voz -eq 'listar') {
  Add-Type -AssemblyName System.Speech
  $sapi = New-Object System.Speech.Synthesis.SpeechSynthesizer
  $sapi.GetInstalledVoices() | ForEach-Object { 'SAPI:' + $_.VoiceInfo.Name + ' | ' + $_.VoiceInfo.Culture }
  Add-Type -AssemblyName System.Runtime.WindowsRuntime
  $null = [Windows.Media.SpeechSynthesis.SpeechSynthesizer, Windows.Media.SpeechSynthesis, ContentType = WindowsRuntime]
  [Windows.Media.SpeechSynthesis.SpeechSynthesizer]::AllVoices | ForEach-Object { 'OneCore:' + $_.DisplayName + ' | ' + $_.Language }
  exit 0
}

$frase = [IO.File]::ReadAllText($Texto, [Text.Encoding]::UTF8)
$tipo, $nome = $Voz.Split(':', 2)

if ($tipo -eq 'SAPI') {
  Add-Type -AssemblyName System.Speech
  $sapi = New-Object System.Speech.Synthesis.SpeechSynthesizer
  $escolhida = $sapi.GetInstalledVoices() | Where-Object { $_.VoiceInfo.Name -like "*$nome*" -and $_.VoiceInfo.Culture.Name -eq 'pt-BR' } | Select-Object -First 1
  if (-not $escolhida) { Write-Error "voz SAPI pt-BR '$nome' não encontrada"; exit 3 }
  $sapi.SelectVoice($escolhida.VoiceInfo.Name)
  # SAPI: de -10 a 10; 1,0 vira 0 e cada 0,1 acima vira um passo.
  $sapi.Rate = [Math]::Max(-10, [Math]::Min(10, [int][Math]::Round(($Velocidade - 1.0) * 10)))
  $sapi.SetOutputToWaveFile($Saida)
  $sapi.Speak($frase)
  $sapi.Dispose()
  exit 0
}

# OneCore (Windows.Media.SpeechSynthesis), pela ponte do WinRT do PowerShell 5.1.
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Media.SpeechSynthesis.SpeechSynthesizer, Windows.Media.SpeechSynthesis, ContentType = WindowsRuntime]
$null = [Windows.Media.SpeechSynthesis.SpeechSynthesisStream, Windows.Media.SpeechSynthesis, ContentType = WindowsRuntime]
$asTask = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
  })[0]
function Esperar($operacao, [Type]$tipoDoResultado) {
  $tarefa = $asTask.MakeGenericMethod($tipoDoResultado).Invoke($null, @($operacao))
  $null = $tarefa.Wait(-1)
  $tarefa.Result
}
$sintetizador = New-Object Windows.Media.SpeechSynthesis.SpeechSynthesizer
$escolhida = [Windows.Media.SpeechSynthesis.SpeechSynthesizer]::AllVoices | Where-Object { $_.DisplayName -like "*$nome*" -and $_.Language -eq 'pt-BR' } | Select-Object -First 1
if (-not $escolhida) { Write-Error "voz OneCore pt-BR '$nome' não encontrada"; exit 3 }
$sintetizador.Voice = $escolhida
try { $sintetizador.Options.SpeakingRate = $Velocidade } catch { }
$fluxo = Esperar ($sintetizador.SynthesizeTextToStreamAsync($frase)) ([Windows.Media.SpeechSynthesis.SpeechSynthesisStream])
$leitura = [System.IO.WindowsRuntimeStreamExtensions]::AsStreamForRead($fluxo)
$arquivo = [IO.File]::Create($Saida)
$leitura.CopyTo($arquivo)
$arquivo.Close()
$leitura.Dispose()
exit 0
