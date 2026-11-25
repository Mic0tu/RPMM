# app/core/observability.py
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

def configure_telemetry(service_name: str):
    # 1. Описываем наш сервис
    resource = Resource.create({"service.name": service_name})
    
    # 2. Настраиваем провайдер трассировки
    provider = TracerProvider(resource=resource)
    
    # 3. Настраиваем экспортер (отправляем на localhost:4318)
    # Обрати внимание на /v1/traces в конце URL — это стандарт OTLP
    otlp_exporter = OTLPSpanExporter(endpoint="http://localhost:4318/v1/traces")
    provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
    
    # 4. Устанавливаем провайдер глобально
    trace.set_tracer_provider(provider)

def instrument_fastapi(app):
    # Эта функция автоматически создаст спаны (span) для всех эндпоинтов FastAPI
    FastAPIInstrumentor.instrument_app(app)