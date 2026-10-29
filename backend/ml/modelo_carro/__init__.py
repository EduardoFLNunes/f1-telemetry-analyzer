"""M1, o modelo do carro para a frente (pedido 37, ADR 0017 e ADR 0022).

Recebe o estado do carro agora (velocidade longitudinal, lateral e guinada) e o
que o piloto faz (volante, acelerador e freio) e devolve o estado depois de um
passo de 50 ms. E uma fisica simples, com poucos parametros, mais um Processo
Gaussiano no residuo dela -- o desenho de Kabzan et al. 2019 e do BayesRace.

* `dados` -- as voltas validas das 5 sessoes, no cronometro do jogo, cortadas
  em trechos e reamostradas;
* `convencoes` -- os sinais de cada canal, conferidos antes de qualquer ajuste;
* `geometria` -- massa, cargas, entre-eixos e a unidade do volante, medidos por
  conta direta;
* `fisica` -- o modelo de bicicleta dinamico (a referencia R1) e o ajuste dele;
* `correcao` -- o Processo Gaussiano no residuo e o corte de "nao conclusivo";
* `validacao` -- as 5 rodadas, a malha aberta, as metricas e o veredito.

Roda offline, como o resto do `ml/`, e nao entra no executavel empacotado.
"""
