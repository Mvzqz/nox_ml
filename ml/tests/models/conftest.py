from collections.abc import Callable

import pytest
from synthetic import Synthetic, synthetic_dataset

from nox_ml.data.inputs import Inputs


@pytest.fixture
def synthetic(make_inputs: Callable[..., Inputs]) -> Synthetic:
    return synthetic_dataset(make_inputs())
