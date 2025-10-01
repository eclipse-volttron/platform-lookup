import json
import sys
from threading import Lock
from fastapi import FastAPI, HTTPException, Depends, Request, Response
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional

app = FastAPI(
    title="Platform Management API",
    description="API for managing platform registrations",
    version="1.0.0"
)

platform_file = "platforms.json"
lock = Lock()
DEFAULT_GROUP = "default"

class PlatformWithIP(BaseModel):
    """Internal model for storing platform data with IP tracking"""
    id: str
    address: str
    public_credentials: str
    group: str
    last_modified_ip: Optional[str] = None

    def to_platform(self) -> "Platform":
        """Convert to Platform model (excluding last_modified_ip)"""
        return Platform(
            id=self.id,
            address=self.address,
            public_credentials=self.public_credentials,
            group=self.group
        )

class Platform(BaseModel):
    id: str = Field(...,
                    description="""
                    # Unique id for the platform.

                    When external platforms refer to an agent on this platform they will use this as a prefix
                    to allow routing of messages to go to the proper location.
                    Only alphanumeric characters, underscores, and hyphens are allowed.
                    The id must be unique across all platforms.
                    """)
    address: str = Field(...,
                    description="""
                    # Address of the platform.

                    This is the address where the platform can be reached.
                    It can be an IP address, a domain name, or a URI.
                    """)
    public_credentials: str = Field(...,
                    description="""
                    # Public credential for the platform.
                    This is the credential that will be used to authenticate with the platform.  For zmq this
                    is the publickey of the server to allow a client to connect to the zap loop.  This may be
                    different for other protocols.
                    """)
    group: str = Field(default=DEFAULT_GROUP,
                    description="""
                    # Group of the platform.

                    This is the group that the platform belongs to.  It is used to group platforms together for
                    routing purposes.  If not specified, the platform will be added to the default group.

                    This will allow partitioning of platforms in the future.
                    """)
    @field_validator('address')
    @classmethod
    def address_must_be_valid(cls, v):
        """Validate that address has a valid format"""
        # Simple URL or IP check - you might want to use proper validation libraries
        import re
        # Basic check for IP or URL-like string
        if not (v.startswith(('http://', 'https://', 'tcp://', 'ipc://')) or
                re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(:\d+)?$', v)):
            raise ValueError("Address must be a valid URL, IP address, or protocol URI")
        return v

    @field_validator('public_credentials')
    @classmethod
    def credential_must_be_valid(cls, v):
        """Validate credential format"""
        if len(v) < 16:  # Example minimum length requirement
            raise ValueError("Public credential must be at least 16 characters long")
        return v

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "id": "platform-123",
                    "address": "tcp://example.com",
                    "public_credentials": "abcdef1234567890",
                    "group": "production"
                }
            ]
        }
    }

def get_platforms():
    """Dependency to get platforms with thread safety"""
    with lock:
        return _load_platforms()

def _store_platforms(platforms):
    """Save platforms to file with proper JSON serialization"""
    # Convert to dict for JSON serialization
    platforms_json = [p.dict() for p in platforms]
    with lock:
        with open(platform_file, "w") as f:
            json.dump(platforms_json, f, indent=2)

def _load_platforms():
    """Load platforms from file with proper deserialization"""
    try:
        with open(platform_file, "r") as f:
            platforms_data = json.load(f)
            return [PlatformWithIP(**p) for p in platforms_data]
    except FileNotFoundError:
        return []

def _get_client_ip(request: Request) -> str:
    """Extract client IP address from request"""
    # Check for forwarded headers first (in case of proxy/load balancer)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Take the first IP if there are multiple
        return forwarded_for.split(",")[0].strip()

    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip

    # Fall back to direct client IP
    return request.client.host if request.client else "unknown"

@app.get("/", tags=["Root"])
async def root():
    """API root endpoint"""
    return {"message": app.title, "version": app.version}

@app.post("/platform", response_model=Platform, tags=["Platforms"])
async def register_platform(platform: Platform, request: Request, response: Response):
    """
    Register a new platform

    This endpoint allows you to register a new platform with the system.

    The following fields must be unique across all platforms:
    - id: The platform's unique identifier
    - address: The platform's network address
    - public_credentials: The platform's public authentication credential

    Returns:
    - 200: If the same IP submits identical platform data
    - 201: If new platform is created or existing platform is updated
    """
    platforms = get_platforms()
    client_ip = _get_client_ip(request)

    # Check if platform already exists
    for i, existing_platform in enumerate(platforms):
        if existing_platform.id == platform.id:
            # Check if this is the same request from the same IP
            if (existing_platform.last_modified_ip == client_ip and
                existing_platform.address == platform.address and
                existing_platform.public_credentials == platform.public_credentials and
                existing_platform.group == platform.group):
                # Same data from same IP - return 200
                response.status_code = 200
                return existing_platform.to_platform()

            # Different data or different IP - check for conflicts with other platforms
            for j, other_platform in enumerate(platforms):
                if j != i:  # Skip the current platform being updated
                    if other_platform.address == platform.address:
                        raise HTTPException(status_code=400, detail=f"Platform with address '{platform.address}' already exists")
                    if other_platform.public_credentials == platform.public_credentials:
                        raise HTTPException(status_code=400, detail=f"Platform with public credential '{platform.public_credentials}' already exists")

            # Update existing platform
            platforms[i] = PlatformWithIP(
                id=platform.id,
                address=platform.address,
                public_credentials=platform.public_credentials,
                group=platform.group,
                last_modified_ip=client_ip
            )
            _store_platforms(platforms)
            response.status_code = 201
            return platforms[i].to_platform()

    # Check for duplicate address or credentials with existing platforms
    if any(p.address == platform.address for p in platforms):
        raise HTTPException(status_code=400, detail=f"Platform with address '{platform.address}' already exists")

    if any(p.public_credentials == platform.public_credentials for p in platforms):
        raise HTTPException(status_code=400, detail=f"Platform with public credential '{platform.public_credentials}' already exists")

    # Create new platform
    new_platform = PlatformWithIP(
        id=platform.id,
        address=platform.address,
        public_credentials=platform.public_credentials,
        group=platform.group,
        last_modified_ip=client_ip
    )
    platforms.append(new_platform)
    _store_platforms(platforms)
    response.status_code = 201
    return new_platform.to_platform()

@app.get("/platform/{platform_id}", response_model=Platform, tags=["Platforms"])
async def read_platform(platform_id: str, platforms: List[PlatformWithIP] = Depends(get_platforms)):
    """
    Get platform details by ID

    Retrieve detailed information about a specific platform
    """
    for platform in platforms:
        if platform.id == platform_id:
            return platform.to_platform()
    raise HTTPException(status_code=404, detail=f"Platform with ID '{platform_id}' not found")

@app.put("/platform/{platform_id}", response_model=Platform, tags=["Platforms"])
async def update_platform(platform_id: str, updated_platform: Platform, request: Request, response: Response):
    """
    Update platform information

    Update an existing platform's details

    Returns:
    - 200: If the same IP submits identical platform data
    - 201: If platform is updated with new data
    """
    platforms = get_platforms()
    client_ip = _get_client_ip(request)

    for i, platform in enumerate(platforms):
        if platform.id == platform_id:
            # Ensure ID doesn't change
            if updated_platform.id != platform_id:
                raise HTTPException(status_code=400, detail="Cannot change platform ID")

            # Check if this is the same request from the same IP
            if (platform.last_modified_ip == client_ip and
                platform.address == updated_platform.address and
                platform.public_credentials == updated_platform.public_credentials and
                platform.group == updated_platform.group):
                # Same data from same IP - return 200
                response.status_code = 200
                return Platform(**platform.dict(exclude={'last_modified_ip'}))

            # Check for conflicts with other platforms (excluding current one)
            for j, other_platform in enumerate(platforms):
                if j != i:  # Skip the current platform being updated
                    if other_platform.address == updated_platform.address:
                        raise HTTPException(status_code=400, detail=f"Platform with address '{updated_platform.address}' already exists")
                    if other_platform.public_credentials == updated_platform.public_credentials:
                        raise HTTPException(status_code=400, detail=f"Platform with public credential '{updated_platform.public_credentials}' already exists")

            # Update platform
            platforms[i] = PlatformWithIP(
                id=updated_platform.id,
                address=updated_platform.address,
                public_credentials=updated_platform.public_credentials,
                group=updated_platform.group,
                last_modified_ip=client_ip
            )
            _store_platforms(platforms)
            response.status_code = 201
            return Platform(**platforms[i].dict(exclude={'last_modified_ip'}))

    raise HTTPException(status_code=404, detail=f"Platform with ID '{platform_id}' not found")

@app.delete("/platform/{platform_id}", tags=["Platforms"])
async def delete_platform(platform_id: str):
    """
    Delete a platform

    Remove a platform from the system
    """
    platforms = get_platforms()
    initial_count = len(platforms)

    platforms = [p for p in platforms if p.id != platform_id]

    if len(platforms) == initial_count:
        raise HTTPException(status_code=404, detail=f"Platform with ID '{platform_id}' not found")

    _store_platforms(platforms)
    return {"message": f"Platform '{platform_id}' deleted successfully"}

@app.get("/platforms", response_model=List[Platform], tags=["Platforms"])
async def list_platforms(platforms: List[PlatformWithIP] = Depends(get_platforms)):
    """
    List all platforms

    Get a list of all registered platforms
    """
    return [p.to_platform() for p in platforms]

def main():
     # Default port
    port = 8000

    # Check if a custom port is provided as a command-line argument
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print("Invalid port number. Using default port 8000.")

    import uvicorn
    uvicorn.run("platform_lookup.app:app", host="0.0.0.0", port=port)

if __name__ == "__main__":
    main()

