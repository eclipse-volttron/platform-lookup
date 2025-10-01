# Platform Lookup Service

A FastAPI-based microservice for managing platform registrations and lookups. This service provides a RESTful API for registering and managing platforms with their associated credentials and network addresses.

## Features

- Platform registration and management
- Thread-safe operations for concurrent access
- Input validation using Pydantic models
- Support for platform grouping
- JSON-based persistent storage
- RESTful API with OpenAPI documentation

## Requirements

- Python 3.x
- FastAPI
- Uvicorn

## Installation

1. From pypi
  
   ```bash
   pip install volttron-platform-lookup
   ```

1. From source code:

   ```bash
   git clone [repository-url]
   cd platform-lookup
   poetry install
   ```


## Usage

1. Start the server:

   ```bash
   volttron-platform-lookup <optional port. defaults to 8000>
   ```

2. The API will be available at `http://localhost:8000`
3. Access the API documentation at `http://localhost:8000/docs`

## API Endpoints

The service provides RESTful endpoints for platform management. All data is exchanged in JSON format.

### Platform Model

Each platform registration includes:

- `id`: Unique identifier for the platform (alphanumeric, underscores, and hyphens allowed)
- `address`: Network address where the platform can be reached (IP, domain, or URI)
- `public_credentials`: Authentication credential (minimum 16 characters)
- `group`: Optional grouping parameter (defaults to "default")

Example platform registration:

```json
{
    "id": "platform-123",
    "address": "tcp://example.com",
    "public_credentials": "abcdef1234567890",
    "group": "production"
}
```

## Data Storage

Platform data is stored in `platforms.json` with thread-safe access mechanisms to prevent race conditions during concurrent operations.

## Security

- Input validation for all API endpoints
- Credential length requirements
- Address format validation
- Thread-safe operations

## Contributing

1. Fork the repository
2. Create a feature branch
3. Submit a pull request

## License

This project is licensed under the Apache License, Version 2.0. See the [LICENSE](LICENSE) file for details.

Copyright 2025 Battelle Memorial Institute

## Disclaimer Notice

This material was prepared as an account of work sponsored by an agency of the
United States Government.  Neither the United States Government nor the United
States Department of Energy, nor Battelle, nor any of their employees, nor any
jurisdiction or organization that has cooperated in the development of these
materials, makes any warranty, express or implied, or assumes any legal
liability or responsibility for the accuracy, completeness, or usefulness or any
information, apparatus, product, software, or process disclosed, or represents
that its use would not infringe privately owned rights.

Reference herein to any specific commercial product, process, or service by
trade name, trademark, manufacturer, or otherwise does not necessarily
constitute or imply its endorsement, recommendation, or favoring by the United
States Government or any agency thereof, or Battelle Memorial Institute. The
views and opinions of authors expressed herein do not necessarily state or
reflect those of the United States Government or any agency thereof.
