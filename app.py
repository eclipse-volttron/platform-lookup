import json
from threading import Lock
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field, field_validator
from typing import List

app = FastAPI(
    title="Platform Management API",
    description="API for managing platform registrations",
    version="1.0.0"
)

platform_file = "platforms.json"
lock = Lock()
DEFAULT_GROUP = "default"

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
    
    model_config = {}
    #model_config = {
    #    "json_schema_extra": {
    #        "examples": [
    #            {
    #                "id": "platform-123",
    #                "address": "tcp://example.com",
    #                "public_credentials": "abcdef1234567890",
    #                "group": "production"
    #            }
    #        ]
    #    }
    #}
    
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
            return [Platform(**p) for p in platforms_data]
    except FileNotFoundError:
        return []

@app.get("/", tags=["Root"])
async def root():
    """API root endpoint"""
    return {"message": app.title, "version": app.version}

@app.post("/platform", response_model=Platform, status_code=201, tags=["Platforms"])
async def register_platform(platform: Platform):
    """
    Register a new platform
    
    This endpoint allows you to register a new platform with the system.
    
    The following fields must be unique across all platforms:
    - id: The platform's unique identifier
    - address: The platform's network address
    - public_credentials: The platform's public authentication credential
    """
    platforms = get_platforms()

    # if platform already exists and is the same, return it
    # TODO: This is a simple check, consider using a more robust method for checking equality
    for itr in platforms:
        if platform.id == itr.id and platform.address == itr.address and platform.public_credentials == itr.public_credentials:
            return platform
    
    # Check for duplicate ID
    if any(p.id == platform.id for p in platforms):
        raise HTTPException(status_code=400, detail=f"Platform with ID '{platform.id}' already exists")
    
    # Check for duplicate address
    if any(p.address == platform.address for p in platforms):
        raise HTTPException(status_code=400, detail=f"Platform with address '{platform.address}' already exists")
    
    # Check for duplicate public_credentials
    if any(p.public_credentials == platform.public_credentials for p in platforms):
        raise HTTPException(status_code=400, detail=f"Platform with public credential '{platform.public_credentials}' already exists")
    
    platforms.append(platform)
    _store_platforms(platforms)
    return platform

@app.get("/platform/{platform_id}", response_model=Platform, tags=["Platforms"])
async def read_platform(platform_id: str, platforms: List[Platform] = Depends(get_platforms)):
    """
    Get platform details by ID
    
    Retrieve detailed information about a specific platform
    """
    for platform in platforms:
        if platform.id == platform_id:
            return platform
    raise HTTPException(status_code=404, detail=f"Platform with ID '{platform_id}' not found")

@app.put("/platform/{platform_id}", response_model=Platform, tags=["Platforms"])
async def update_platform(platform_id: str, updated_platform: Platform):
    """
    Update platform information
    
    Update an existing platform's details
    """
    platforms = get_platforms()
    
    for i, platform in enumerate(platforms):
        if platform.id == platform_id:
            # Ensure ID doesn't change
            if updated_platform.id != platform_id:
                raise HTTPException(status_code=400, detail="Cannot change platform ID")
            
            platforms[i] = updated_platform
            _store_platforms(platforms)
            return updated_platform
            
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
async def list_platforms(platforms: List[Platform] = Depends(get_platforms)):
    """
    List all platforms
    
    Get a list of all registered platforms
    """
    return platforms

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)
