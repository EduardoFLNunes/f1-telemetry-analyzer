from __future__ import annotations

from typing import Dict, List, Optional

from .assisted_analysis_models import DrivingKnowledgeConcept


class DrivingKnowledgeBase:
    def __init__(self):
        self._concepts: Dict[str, DrivingKnowledgeConcept] = {
            "EARLY_BRAKING": self._concept(
                "EARLY_BRAKING",
                "Freada antecipada",
                "Transferencia de peso longitudinal antes da zona ideal",
                "Threshold braking no ponto de referencia",
                ["brakeStartDeltaM negativo", "velocidade de entrada abaixo ou tempo perdido antes do apex"],
                "O piloto transfere carga para frente cedo demais e prolonga a fase lenta.",
                ["brakeStartDeltaM", "entrySpeedDeltaKmh", "segmentTimeDeltaS"],
                "Atrase o ponto inicial mantendo a mesma pressao maxima de freio, sem transformar a entrada em coasting.",
            ),
            "LATE_BRAKING": self._concept(
                "LATE_BRAKING",
                "Freada tardia",
                "Pico de demanda longitudinal muito perto da entrada",
                "Threshold braking com margem para rotacionar",
                ["brakeStartDeltaM positivo", "entrySpeedDeltaKmh positivo", "minSpeedDeltaKmh positivo"],
                "O carro chega carregado demais na entrada e usa aderencia longitudinal quando deveria comecar a rotacionar.",
                ["brakeStartDeltaM", "entrySpeedDeltaKmh", "minSpeedDeltaKmh"],
                "Antecipe poucos metros e busque uma pressao inicial forte, com release progressivo antes do apex.",
            ),
            "BRAKE_HELD_TOO_LONG": self._concept(
                "BRAKE_HELD_TOO_LONG",
                "Freio mantido tempo demais na entrada",
                "Carga dianteira excessiva durante rotacao",
                "Trail braking progressivo",
                ["brakeReleaseDeltaM positivo", "brake ainda ativo no apex", "velocidade minima baixa"],
                "O freio continua prendendo o carro na fase em que a plataforma deveria liberar rotacao.",
                ["brakeReleaseDeltaM", "brakeAtApex", "minSpeedDeltaKmh"],
                "Comece o release mais cedo e reduza a pressao conforme aumenta o angulo de volante.",
            ),
            "ABRUPT_BRAKE_RELEASE": self._concept(
                "ABRUPT_BRAKE_RELEASE",
                "Liberacao brusca do freio",
                "Transferencia de peso rapida para tras",
                "Controle progressivo de freio",
                ["taxa de release alta", "queda rapida de freio", "instabilidade de yaw"],
                "A plataforma perde carga dianteira de uma vez, reduzindo precisao e rotacao.",
                ["brakeReleaseRate", "yawRate", "stabilityScore"],
                "Solte o freio em rampa, mantendo pequena pressao ate o carro aceitar a direcao.",
            ),
            "EARLY_BRAKE_RELEASE": self._concept(
                "EARLY_BRAKE_RELEASE",
                "Liberacao precoce do freio",
                "Perda de carga dianteira antes da rotacao",
                "Trail braking ate a entrada",
                ["brakeReleaseDeltaM negativo", "baixo yawRate no apex", "entrada lenta"],
                "O carro fica sem carga no eixo dianteiro antes de completar a rotacao.",
                ["brakeReleaseDeltaM", "meanAbsYawRate", "minSpeedDeltaKmh"],
                "Mantenha pressao residual por mais alguns metros para ajudar o carro a apontar.",
            ),
            "BRAKE_REAPPLIED_WITH_STEERING": self._concept(
                "BRAKE_REAPPLIED_WITH_STEERING",
                "Reaplicacao de freio com volante alto",
                "Saturacao do circulo de atrito",
                "Separar correcao de velocidade e rotacao",
                ["pico secundario de freio", "volante alto", "lateralG elevado"],
                "O pneu e solicitado a frear e virar ao mesmo tempo depois da entrada, aumentando subesterco ou instabilidade.",
                ["brakeReapplyWithSteering", "meanAbsSteering", "frictionUsagePeak"],
                "Resolva a velocidade antes e evite tocar novamente no freio quando ja ha volante significativo.",
            ),
            "AGGRESSIVE_ENTRY": self._concept(
                "AGGRESSIVE_ENTRY",
                "Entrada agressiva",
                "Taxa de esterçamento e yaw acima da aderencia disponivel",
                "Entrada com volante progressivo",
                ["steeringRate alto", "yawRate alto", "lineDeviation alto"],
                "A mudanca rapida de direcao consome aderencia lateral antes do carro estabilizar.",
                ["maxSteeringRate", "maxYawRate", "referenceLineDeviationM"],
                "Reduza a velocidade de aplicacao do volante e deixe o carro assumir carga lateral em uma rampa.",
            ),
            "SLOW_ENTRY": self._concept(
                "SLOW_ENTRY",
                "Entrada lenta",
                "Margem de aderencia nao utilizada",
                "Entrada com velocidade minima eficiente",
                ["entrySpeedDeltaKmh negativo", "minSpeedDeltaKmh negativo"],
                "O piloto entra com margem demais e perde tempo antes de carregar lateralmente o pneu.",
                ["entrySpeedDeltaKmh", "minSpeedDeltaKmh", "segmentTimeDeltaS"],
                "Leve mais velocidade ate a primeira parte da curva, mantendo o mesmo ponto de apex.",
            ),
            "ENTRY_OVERSPEED": self._concept(
                "ENTRY_OVERSPEED",
                "Excesso de velocidade na entrada",
                "Excesso de energia cinetica na fase de rotacao",
                "Entrada no limite sem saturar o eixo dianteiro",
                ["entrySpeedDeltaKmh positivo", "linha abre", "minSpeedDeltaKmh alto"],
                "O carro chega rapido demais e precisa gastar metros corrigindo raio ou reduzindo velocidade.",
                ["entrySpeedDeltaKmh", "lineDeviationDeltaM", "minSpeedDeltaKmh"],
                "Reduza ligeiramente a velocidade de entrada e priorize apontar o carro mais cedo.",
            ),
            "EARLY_APEX": self._concept(
                "EARLY_APEX",
                "Apex antecipado",
                "Raio de curva fechado cedo demais",
                "Apex que preserva a saida",
                ["apexDeltaM negativo", "perda de velocidade de saida", "linha abre na saida"],
                "O carro encurta a entrada e fica sem pista/raio para acelerar na saida.",
                ["apexDeltaM", "exitSpeedDeltaKmh", "phaseLineDeviationDeltaM.exit"],
                "Atrase o ponto de corda e aceite uma entrada um pouco mais aberta para liberar a saida.",
            ),
            "LATE_APEX": self._concept(
                "LATE_APEX",
                "Apex tardio",
                "Rotacao atrasada",
                "Apex alinhado com a aceleracao",
                ["apexDeltaM positivo", "retomada tardia", "saida lenta"],
                "O carro demora a apontar e atrasa a fase de aceleracao.",
                ["apexDeltaM", "throttlePickupDeltaM", "exitSpeedDeltaKmh"],
                "Inicie a rotacao antes ou mantenha trail braking suave para chegar ao apex no tempo correto.",
            ),
            "ENTRY_UNDERSTEER": self._concept(
                "ENTRY_UNDERSTEER",
                "Subesterco na entrada",
                "Eixo dianteiro saturado na combinacao freio+volante",
                "Trail braking com release progressivo",
                ["volante alto", "yawRate baixo", "linha abre na entrada"],
                "O volante pede mais giro do que o eixo dianteiro consegue entregar.",
                ["meanAbsSteering", "meanAbsYawRate", "referenceLineDeviationM"],
                "Reduza a demanda simultanea de freio e volante ou alivie a entrada para recuperar frente.",
            ),
            "MID_CORNER_UNDERSTEER": self._concept(
                "MID_CORNER_UNDERSTEER",
                "Subesterco no meio da curva",
                "Pneu dianteiro fora do pico de aderencia lateral",
                "Manter raio e velocidade minima sem arrastar frente",
                ["volante sustentado alto", "yawRate baixo", "L/desvio crescente no apex"],
                "O carro nao fecha o raio no miolo e obriga espera antes de acelerar.",
                ["meanAbsSteering", "meanAbsYawRate", "phaseLineDeviationDeltaM.apex"],
                "Diminua a velocidade minima ou ajude a rotacao com release de freio mais refinado.",
            ),
            "ENTRY_OVERSTEER": self._concept(
                "ENTRY_OVERSTEER",
                "Sobresterco na entrada",
                "Excesso de yaw na transferencia para frente",
                "Rotacao controlada no trail braking",
                ["yawRate alto", "correcao de volante", "longitudinalG negativo"],
                "A traseira gira mais rapido que o necessario durante a entrada.",
                ["maxYawRate", "maxSteeringRate", "minLongitudinalG"],
                "Suavize o trail braking final e reduza transferencia brusca para frente.",
            ),
            "EXIT_OVERSTEER": self._concept(
                "EXIT_OVERSTEER",
                "Sobresterco na saida",
                "Excesso de torque com pneu ainda carregado lateralmente",
                "Acelerador progressivo na saida",
                ["throttleApplicationRate alto", "yawRate alto", "correcao de volante"],
                "A aceleracao chega antes do carro estar suficientemente reto.",
                ["throttleApplicationRate", "maxYawRate", "maxSteeringRate"],
                "Aplique acelerador em rampa e espere reduzir o angulo de volante antes de carga total.",
            ),
            "AGGRESSIVE_THROTTLE": self._concept(
                "AGGRESSIVE_THROTTLE",
                "Acelerador agressivo",
                "Transferencia de peso para tras e saturacao traseira",
                "Controle progressivo de acelerador",
                ["throttleApplicationRate alto", "frictionUsage alto", "instabilidade de saida"],
                "O torque aumenta mais rapido que a aderencia traseira disponivel.",
                ["throttleApplicationRate", "frictionUsagePeak", "stabilityScore"],
                "Transforme a retomada em rampa; acelere conforme o volante abre.",
            ),
            "LATE_THROTTLE": self._concept(
                "LATE_THROTTLE",
                "Retomada tardia",
                "Aderencia longitudinal subutilizada na saida",
                "Aceleracao assim que o carro aponta",
                ["throttlePickupDeltaM positivo", "coasting alto", "saida lenta"],
                "O carro ja poderia receber torque, mas fica em fase neutra por metros demais.",
                ["throttlePickupDeltaM", "coastingDeltaM", "exitSpeedDeltaKmh"],
                "Procure o primeiro ponto seguro de acelerador e aumente a carga progressivamente.",
            ),
            "EARLY_THROTTLE": self._concept(
                "EARLY_THROTTLE",
                "Aceleracao precoce",
                "Torque aplicado antes do fim da rotacao",
                "Acelerador somente com plataforma apontada",
                ["throttlePickupDeltaM negativo", "saida instavel", "linha abre"],
                "O carro recebe torque enquanto ainda pede muito pneu lateral.",
                ["throttlePickupDeltaM", "lineDeviationDeltaM", "stabilityScore"],
                "Espere o carro terminar de apontar ou reduza a rampa inicial de acelerador.",
            ),
            "EXCESS_COASTING": self._concept(
                "EXCESS_COASTING",
                "Excesso de coasting",
                "Nenhum eixo usa plenamente a aderencia disponivel",
                "Transicao freio-acelerador sem zona morta longa",
                ["throttle baixo", "brake baixo", "distancia neutra acima da referencia"],
                "A volta perde metros sem frear, virar com carga ou acelerar.",
                ["coastingDeltaM", "throttlePickupDeltaM", "segmentTimeDeltaS"],
                "Reduza a zona neutra: ou finalize a frenagem com trail braking, ou inicie acelerador suave.",
            ),
            "EXCESS_STEERING_CORRECTION": self._concept(
                "EXCESS_STEERING_CORRECTION",
                "Excesso de correcao no volante",
                "Instabilidade de plataforma e oscilacao de aderencia",
                "Input de volante estavel e progressivo",
                ["steeringRate alto", "mudancas de sinal", "yawRate oscilando"],
                "O carro exige correcoes que aumentam arrasto e deixam a saida irregular.",
                ["maxSteeringRate", "steeringCorrectionCount", "meanAbsYawRate"],
                "Suavize a entrada e seja mais paciente no acelerador para reduzir correcoes.",
            ),
            "LOW_ROTATION": self._concept(
                "LOW_ROTATION",
                "Baixa rotacao do carro",
                "YawRate insuficiente para o raio desejado",
                "Rotacao induzida por trail braking e timing de apex",
                ["yawRate abaixo da referencia", "apex tardio", "retomada tardia"],
                "O carro demora a apontar para a saida e prende o acelerador.",
                ["meanAbsYawRate", "apexDeltaM", "throttlePickupDeltaM"],
                "Use trail braking mais limpo ou uma entrada ligeiramente mais decisiva para apontar o carro.",
            ),
            "UNSTABLE_EXIT": self._concept(
                "UNSTABLE_EXIT",
                "Saida instavel",
                "Transferencia lateral e longitudinal competindo na tracao",
                "Acelerador progressivo com volante abrindo",
                ["yawRate alto na saida", "steeringRate alto", "throttle alto"],
                "A saida alterna entre tracao e correcao, custando velocidade na reta posterior.",
                ["maxYawRate", "maxSteeringRate", "throttleApplicationRate"],
                "Atrase carga total de acelerador ate o carro ficar mais reto e estavel.",
            ),
            "POOR_EXIT": self._concept(
                "POOR_EXIT",
                "Saida ruim",
                "Baixa velocidade e alinhamento comprometido na reta posterior",
                "Saida de curva com aceleracao progressiva e uso completo de pista",
                ["exitSpeedDeltaKmh negativo", "fullThrottleDeltaM positivo", "perda continua na reta posterior"],
                "A curva termina com menos velocidade util e a perda se propaga pela reta seguinte.",
                ["exitSpeedDeltaKmh", "fullThrottleDeltaM", "throttlePickupDeltaM", "segmentTimeDeltaS"],
                "Priorize apontar o carro antes da saida e antecipe uma rampa de acelerador que nao force correcoes.",
            ),
            "TRAJECTORY_DEVIATION": self._concept(
                "TRAJECTORY_DEVIATION",
                "Desvio de trajetoria",
                "Raio e uso de pista diferentes da referencia",
                "Linha que preserva velocidade e angulo de saida",
                ["desvio lateral acima da referencia", "perda de tempo local"],
                "A linha escolhida aumenta distancia, fecha raio ou atrasa aceleracao.",
                ["lineDeviationDeltaM", "phaseLineDeviationDeltaM"],
                "Compare o ponto de entrada, apex e abertura de saida; ajuste a linha antes de mexer em inputs.",
            ),
        }

    def get(self, code: str) -> Optional[DrivingKnowledgeConcept]:
        return self._concepts.get(code)

    def all(self) -> List[DrivingKnowledgeConcept]:
        return list(self._concepts.values())

    def enrich_error(self, error):
        concept = self.get(error.code)
        if not concept:
            return error
        error.concept = concept.physical_concept
        error.technique = concept.driving_technique
        error.expected_telemetry = concept.expected_telemetry
        error.feedback = f"{error.description} {concept.feedback_hint}"
        if not error.physical_behavior:
            error.physical_behavior = concept.likely_error
        return error

    @staticmethod
    def _concept(
        code: str,
        label: str,
        physical_concept: str,
        driving_technique: str,
        expected_telemetry: List[str],
        likely_error: str,
        evidence_keys: List[str],
        feedback_hint: str,
    ) -> DrivingKnowledgeConcept:
        return DrivingKnowledgeConcept(
            code=code,
            label=label,
            physical_concept=physical_concept,
            driving_technique=driving_technique,
            expected_telemetry=expected_telemetry,
            likely_error=likely_error,
            evidence_keys=evidence_keys,
            feedback_hint=feedback_hint,
        )
