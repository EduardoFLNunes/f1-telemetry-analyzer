"""Testes das redes -- a metade do subsistema que `test_ml_pipeline` nao cobria.

A auditoria encontrou `ml/models/` inteiro sem teste: se a LSTM parasse de
aprender, a suite continuaria verde. Estes testes fecham isso, e o fazem sem
depender dos 11 GB de telemetria nem dos pesos treinados -- treinam uma rede
minuscula sobre um sinal sintetico em segundos.

O sinal e escolhido para que a resposta certa seja conhecida: o alvo e uma
funcao determinista da entrada, entao uma rede que aprende tem de chegar perto
e uma que nao aprende nao tem como.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ml.features.scaling import fit_scaler, fit_target_transform
from ml.models.lstm import TORCH_AVAILABLE, LSTMConfig, TrackSequenceLSTM, count_parameters
from ml.models.sequences import SequenceSet, TaskSpec, drop_warmup, step_time, with_warmup

if TORCH_AVAILABLE:
    from ml.models.training import TrainConfig, evaluate, load_model, save_model, train_model
    from ml.validation.learning import mean_predictor_error, output_spread, untrained_twin

WINDOW = 24
CHANNELS = 3


def synthetic_sequences(count: int, seed: int = 0, noise: float = 0.02) -> SequenceSet:
    """Janelas em que o alvo e uma funcao conhecida da entrada.

    `alvo = sin(x0 acumulado) + x1`, ou seja: depende do passado da sequencia
    (o acumulado) e do instante (o termo direto). Uma rede sem memoria acerta a
    segunda parte e erra a primeira, o que separa "aprendeu" de "decorou a
    media".
    """
    generator = np.random.default_rng(seed)
    inputs = generator.normal(size=(count, WINDOW, CHANNELS)).astype(np.float32)
    accumulated = np.cumsum(inputs[:, :, 0], axis=1) / WINDOW
    targets = (np.sin(3.0 * accumulated) + 0.5 * inputs[:, :, 1]).astype(np.float32)
    targets = targets + generator.normal(scale=noise, size=targets.shape).astype(np.float32)
    return SequenceSet(
        inputs=inputs,
        targets=targets[:, :, None],
        lap_ids=np.array([f"lap{i % 4}" for i in range(count)], dtype=object),
        start_index=np.zeros(count, dtype=int),
        input_columns=("a", "b", "c"),
        target_columns=("valor",),
    )


TINY_TASK = TaskSpec(name="teste", inputs=("a", "b", "c"), targets=("valor",), window=WINDOW, stride=4)


def tiny_config() -> LSTMConfig:
    return LSTMConfig(
        input_size=CHANNELS,
        output_size=1,
        hidden_size=12,
        layers=1,
        dropout=0.0,
        bidirectional=False,
        target_columns=("valor",),
        input_columns=("a", "b", "c"),
    )


@unittest.skipUnless(TORCH_AVAILABLE, "PyTorch nao instalado nesta venv")
class ArchitectureTest(unittest.TestCase):
    def test_parameter_count_matches_the_closed_form(self):
        config = tiny_config()
        model = TrackSequenceLSTM(config)
        hidden, size = config.hidden_size, config.input_size
        expected = 4 * hidden * (size + hidden) + 8 * hidden + hidden * config.output_size + config.output_size
        self.assertEqual(count_parameters(model), expected)

    def test_bidirectional_doubles_the_head_input(self):
        config = tiny_config()
        config = LSTMConfig(**{**config.to_dict(), "bidirectional": True})
        model = TrackSequenceLSTM(config)
        self.assertEqual(model.head.in_features, 2 * config.hidden_size)

    def test_unit_channels_leave_the_head_bounded(self):
        # `brake` esta na lista de canais unitarios; `lateral` nao.
        config = LSTMConfig(
            input_size=CHANNELS, output_size=2, hidden_size=8, layers=1,
            bidirectional=False, target_columns=("brake", "lateral"),
        )
        model = TrackSequenceLSTM(config)
        # Pesos grandes levariam qualquer saida linear para fora de [0, 1].
        with_large_weights = model.state_dict()
        with_large_weights["head.bias"] = with_large_weights["head.bias"] + 50.0
        model.load_state_dict(with_large_weights)
        output = model.predict(np.zeros((1, WINDOW, CHANNELS), dtype=np.float32))
        self.assertLessEqual(float(output[..., 0].max()), 1.0)
        self.assertGreater(float(output[..., 1].max()), 1.0)

    def test_prediction_batches_match_a_single_pass(self):
        model = TrackSequenceLSTM(tiny_config())
        data = np.random.default_rng(1).normal(size=(37, WINDOW, CHANNELS)).astype(np.float32)
        np.testing.assert_allclose(
            model.predict(data, batch_size=8), model.predict(data, batch_size=1024), atol=1e-6
        )


@unittest.skipUnless(TORCH_AVAILABLE, "PyTorch nao instalado nesta venv")
class TrainingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.train = synthetic_sequences(256, seed=1)
        cls.validation = synthetic_sequences(64, seed=2)
        cls.test = synthetic_sequences(64, seed=3)
        cls.trained = train_model(
            TINY_TASK,
            cls.train,
            cls.validation,
            model_config=tiny_config(),
            config=TrainConfig(epochs=25, batch_size=32, patience=25, learning_rate=1e-2),
            verbose=False,
        )

    def test_training_reduces_the_loss(self):
        history = self.trained.history
        self.assertGreater(len(history), 1)
        self.assertLess(history[-1]["train_loss"], history[0]["train_loss"])

    def test_validation_loss_also_falls(self):
        history = self.trained.history
        self.assertLess(min(h["validation_loss"] for h in history), history[0]["validation_loss"])

    def test_the_best_epoch_is_kept_not_the_last(self):
        losses = [h["validation_loss"] for h in self.trained.history]
        self.assertAlmostEqual(self.trained.best_validation, min(losses), places=6)

    def test_training_beats_untrained_weights(self):
        trained_error = evaluate(self.trained, self.test)["mae_valor"]
        untrained_error = evaluate(untrained_twin(self.trained), self.test)["mae_valor"]
        self.assertLess(trained_error, untrained_error)

    def test_training_beats_predicting_the_mean(self):
        trained_error = evaluate(self.trained, self.test)["mae_valor"]
        self.assertLess(trained_error, mean_predictor_error(self.train, self.test, 0))

    def test_the_output_is_not_constant(self):
        spread = output_spread(self.trained, self.test)["valor"]
        self.assertGreater(spread["output_std_ratio"], 0.5)

    def test_different_inputs_give_different_outputs(self):
        first = self.test.inputs[0]
        second = self.test.inputs[1]
        output_a = self.trained.predict(first[None, ...])
        output_b = self.trained.predict(second[None, ...])
        self.assertFalse(np.allclose(output_a, output_b))

    def test_a_saved_model_predicts_the_same_after_loading(self):
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            save_model(self.trained, Path(directory))
            restored = load_model(Path(directory))
            np.testing.assert_allclose(
                self.trained.predict(self.test.inputs[:8]),
                restored.predict(self.test.inputs[:8]),
                atol=1e-6,
            )

    def test_the_scaler_is_fitted_on_training_data_only(self):
        scaler = fit_scaler(self.train.inputs, self.train.input_columns)
        np.testing.assert_allclose(
            scaler.mean, self.train.inputs.reshape(-1, CHANNELS).mean(axis=0), atol=1e-5
        )


@unittest.skipUnless(TORCH_AVAILABLE, "torch ausente")
class ShufflingTest(unittest.TestCase):
    """A ordem das amostras nao pode depender do RNG global.

    O `RandomSampler`, sem gerador proprio, sorteia a partir do RNG global do
    torch -- que o dropout tambem consome a cada passagem. Sem o gerador, mexer
    em qualquer outra fonte de aleatoriedade reordena o treino inteiro, e duas
    corridas "com a mesma semente" deixam de ser a mesma corrida.
    """

    def _first_batch(self, burn: int):
        import torch

        from ml.models.training import TrainConfig, _loaders

        dataset = synthetic_sequences(64, seed=7)
        scaler = fit_scaler(dataset.inputs, dataset.input_columns)
        transform = fit_target_transform(
            dataset.targets.reshape(-1, dataset.targets.shape[-1]), TINY_TASK.targets
        )
        torch.manual_seed(0)
        torch.randn(burn)  # simula o que o dropout teria consumido
        loader, _ = _loaders(dataset, None, scaler, transform, TrainConfig(batch_size=8))
        return next(iter(loader))[0].numpy()

    def test_batch_order_survives_a_disturbed_global_rng(self):
        np.testing.assert_array_equal(self._first_batch(0), self._first_batch(4096))


class TargetTransformTest(unittest.TestCase):
    def test_unit_channels_pass_through_untouched(self):
        values = np.array([[0.0, 0.5, 1.0]]).T
        transform = fit_target_transform(values, ("brake",))
        np.testing.assert_allclose(transform.forward(values), values)

    def test_log_channels_round_trip(self):
        values = np.linspace(0.01, 0.2, 40)[:, None]
        transform = fit_target_transform(values, ("step_time_s",))
        np.testing.assert_allclose(transform.inverse(transform.forward(values)), values, rtol=1e-6)

    def test_standard_channels_round_trip(self):
        values = np.linspace(-8.0, 9.0, 40)[:, None]
        transform = fit_target_transform(values, ("lateral",))
        np.testing.assert_allclose(transform.inverse(transform.forward(values)), values, rtol=1e-6)


class WindowingTest(unittest.TestCase):
    def test_warmup_wraps_the_closed_lap(self):
        data = np.arange(30, dtype=float).reshape(1, 10, 3)
        padded = with_warmup(data, 4)
        self.assertEqual(padded.shape[1], 18)
        np.testing.assert_allclose(padded[0, :4], data[0, -4:])
        np.testing.assert_allclose(padded[0, -4:], data[0, :4])

    def test_dropping_the_warmup_restores_the_shape(self):
        data = np.arange(30, dtype=float).reshape(1, 10, 3)
        np.testing.assert_allclose(drop_warmup(with_warmup(data, 4), 4), data)

    def test_zero_warmup_is_a_no_op(self):
        data = np.arange(30, dtype=float).reshape(1, 10, 3)
        np.testing.assert_allclose(with_warmup(data, 0), data)

    def test_step_time_rejects_non_positive_steps(self):
        import pandas as pd

        frame = pd.DataFrame({"elapsed_s": [0.0, 0.1, 0.1, 0.3], "lap_time_s": [0.4] * 4})
        steps = step_time(frame)
        self.assertTrue(np.isnan(steps[1]), "um passo de tempo zero deve virar NaN, nao zero")
        self.assertTrue(np.all(steps[~np.isnan(steps)] > 0))


if __name__ == "__main__":
    unittest.main()
