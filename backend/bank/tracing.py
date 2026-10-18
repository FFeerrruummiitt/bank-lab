"""Tracing is enabled only in WSGI workers, never in migrations or test commands."""
import os
from functools import wraps
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode


def configure_tracing():
    if os.environ.get('BANK_TRACING_ENABLED', '').lower() != 'true':
        return
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.django import DjangoInstrumentor
    from opentelemetry.instrumentation.psycopg import PsycopgInstrumentor
    provider = TracerProvider(resource=Resource.create({
        'service.name': 'bank-api', 'deployment.environment.name': 'local',
    }))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(timeout=3),
                                                 schedule_delay_millis=500))
    trace.set_tracer_provider(provider)
    DjangoInstrumentor().instrument()
    PsycopgInstrumentor().instrument(capture_parameters=False)


def trace_fields():
    context = trace.get_current_span().get_span_context()
    if not context.is_valid:
        return {}
    return {'trace_id': format(context.trace_id, '032x'), 'span_id': format(context.span_id, '016x')}


def traced(name):
    def decorate(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            with trace.get_tracer('bank.business').start_as_current_span(
                    name, record_exception=False, set_status_on_exception=False) as span:
                try:
                    result = function(*args, **kwargs)
                except Exception as error:
                    span.set_attribute('error.type', type(error).__name__)
                    span.set_status(Status(StatusCode.ERROR))
                    raise
                return result
        return wrapped
    return decorate
