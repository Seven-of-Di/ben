import os

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.propagate import set_global_textmap
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

tracing_enabled = os.environ.get("OTEL_SERVICE_NAME") != None

if tracing_enabled:
    provider = TracerProvider()
    processor = BatchSpanProcessor(OTLPSpanExporter())

    provider.add_span_processor(processor)

    trace.set_tracer_provider(provider)

    set_global_textmap(TraceContextTextMapPropagator())

tracer = trace.get_tracer_provider().get_tracer(__name__)
