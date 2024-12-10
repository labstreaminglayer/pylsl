"""Python API for the lab streaming layer.

The lab streaming layer provides a set of functions to make instrument data
accessible in real time within a lab network. From there, streams can be
picked up by recording programs, viewing programs or custom experiment
applications that access data streams in real time.

The API covers two areas:
- The "push API" allows to create stream outlets and to push data (regular
  or irregular measurement time series, event data, coded audio/video frames,
  etc.) into them.
- The "pull API" allows to create stream inlets and read time-synched
  experiment data from them (for recording, viewing or experiment control).

"""

from .__version__ import __version__ as __version__
from .resolve import ContinuousResolver as ContinuousResolver
from .resolve import resolve_streams as resolve_streams
from .resolve import resolve_bypred as resolve_bypred
from .resolve import resolve_byprop as resolve_byprop
from .info import StreamInfo as StreamInfo
from .inlet import StreamInlet as StreamInlet
from .outlet import StreamOutlet as StreamOutlet
from .util import IRREGULAR_RATE as IRREGULAR_RATE
from .util import FOREVER as FOREVER
from .util import proc_none as proc_none
from .util import proc_clocksync as proc_clocksync
from .util import proc_dejitter as proc_dejitter
from .util import proc_monotonize as proc_monotonize
from .util import proc_threadsafe as proc_threadsafe
from .util import proc_ALL as proc_ALL
from .util import protocol_version as protocol_version
from .util import library_version as library_version
from .util import library_info as library_info
from .util import local_clock as local_clock
from .lib import cf_int8 as cf_int8
from .lib import cf_int16 as cf_int16
from .lib import cf_int32 as cf_int32
from .lib import cf_int64 as cf_int64
from .lib import cf_float32 as cf_float32
from .lib import cf_double64 as cf_double64
from .lib import cf_string as cf_string
