"""Cache of trained kernels: one weights file and one JSON per set of training parameters.

Training takes about 15 minutes on CPU and its result does not depend on the data, so it is done once per
`PinnParams.training_key` and reused by every run. The JSON next to the weights keeps the parameters, the
training log and the validation against the exact solution. File I/O lives here, not in the model.
"""

import json
from pathlib import Path

import torch

from nox_ml.models.pinn.kernel import KernelNet, Progress, TrainedKernel, train_kernel
from nox_ml.models.pinn.params import PinnParams


class KernelCache:
    def __init__(self, directory: Path):
        self.directory = directory

    def weights_path(self, params: PinnParams) -> Path:
        return self.directory / f"kernel-{params.training_key()}.pt"

    def info_path(self, params: PinnParams) -> Path:
        return self.weights_path(params).with_suffix(".json")

    def save(self, kernel: TrainedKernel) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        torch.save(kernel.net.state_dict(), self.weights_path(kernel.params))
        info = {
            "training_key": kernel.params.training_key(),
            "params": kernel.params.model_dump(),
            "seconds": kernel.seconds,
            "log": kernel.log,
            "validation": kernel.validation,
        }
        self.info_path(kernel.params).write_text(json.dumps(info, indent=2) + "\n")

    def load(self, params: PinnParams) -> TrainedKernel | None:
        """The cached kernel of `params`, or None if it was never trained."""
        weights, info_file = self.weights_path(params), self.info_path(params)
        if not (weights.exists() and info_file.exists()):
            return None
        net = KernelNet(params.layers, params.width)
        net.load_state_dict(torch.load(weights, weights_only=True))
        net.eval()
        info = json.loads(info_file.read_text())
        log = [(phase, step, loss, secs) for phase, step, loss, secs in info["log"]]
        return TrainedKernel(net, params, log, info["seconds"], info["validation"])

    def get(self, params: PinnParams, progress: Progress | None = None) -> TrainedKernel:
        """The cached kernel of `params`; trained and saved first if it is not there."""
        kernel = self.load(params)
        if kernel is None:
            kernel = train_kernel(params, progress)
            self.save(kernel)
        return kernel


BUNDLED = KernelCache(Path(__file__).parent / "bundled")  # the network of the default parameters
_IN_MEMORY: dict[str, TrainedKernel] = {}


def obtain_kernel(params: PinnParams, directory: Path | None = None, progress: Progress | None = None):
    """The trained kernel of `params`, from the first place that has it: memory (shared by every model of the
    process, so a leave-one-out refit does not train again), the bundled default network, the disk cache
    `directory`; else trained here (and saved in `directory`, if given). The kernel is a function of the
    training fields of `params` alone, never of the data, so none of this can leak a held-out station."""
    key = params.training_key()
    if key not in _IN_MEMORY:
        kernel = BUNDLED.load(params)
        if kernel is None:
            kernel = (
                KernelCache(directory).get(params, progress) if directory else train_kernel(params, progress)
            )
        _IN_MEMORY[key] = kernel
    return _IN_MEMORY[key]
