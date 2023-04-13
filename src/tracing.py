from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
)

provider = TracerProvider()
processor = BatchSpanProcessor(OTLPSpanExporter())

provider.add_span_processor(processor)

trace.set_tracer_provider(provider)

tracer = trace.get_tracer_provider().get_tracer(__name__)
