import torch
from contextlib import contextmanager


def get_cast_dtype(precision):
    """Get the appropriate dtype for casting based on precision setting."""
    if precision == 'amp':
        return torch.float16
    elif precision == 'amp_bfloat16':
        return torch.bfloat16
    else:
        return torch.float32

@contextmanager
def no_op_context():
    """A no-op context manager for when autocast is disabled."""
    yield

def get_autocast(precision):
    """Get the appropriate autocast context manager based on precision setting."""
    if precision == 'amp':
        return torch.cuda.amp.autocast
    elif precision == 'amp_bfloat16':
        return lambda: torch.cuda.amp.autocast(dtype=torch.bfloat16)
    else:
        return no_op_context
