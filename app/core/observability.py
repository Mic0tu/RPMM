# app/core/observability.py
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

def configure_telemetry(service_name: str):
    resource = Resource.create({"service.name": service_name})
    
    provider = TracerProvider(resource=resource)
    
    otlp_exporter = OTLPSpanExporter(endpoint="http://localhost:4318/v1/traces")
    provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
    
    trace.set_tracer_provider(provider)

def instrument_fastapi(app):
    FastAPIInstrumentor.instrument_app(app)