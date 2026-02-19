FROM python:3.12-slim

WORKDIR /app

# Install Python gRPC dependencies
COPY server/python-tool/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the gRPC stubs and server
COPY server/python-tool/amplifier_module_pb2.py server/python-tool/amplifier_module_pb2_grpc.py server/python-tool/server.py ./

# Copy the code_analysis module into a location the server can find
RUN mkdir -p /app/python
COPY python/code_analysis.py /app/python/code_analysis.py

EXPOSE 50053

CMD ["python", "server.py"]
