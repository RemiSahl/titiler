# Module titiler.core.middleware

Titiler middlewares.

None

## Classes

### CacheControlMiddleware

```python3
class CacheControlMiddleware(
    app: Callable[[MutableMapping[str, Any], Callable[[], Awaitable[MutableMapping[str, Any]]], Callable[[MutableMapping[str, Any]], Awaitable[NoneType]]], Awaitable[NoneType]],
    cachecontrol: Union[str, NoneType] = None,
    cachecontrol_max_http_code: Union[int, NoneType] = 500,
    exclude_path: Union[Set[str], NoneType] = None
)
```

#### Ancestors (in MRO)

* starlette.middleware.base.BaseHTTPMiddleware

#### Methods

    
#### dispatch

```python3
def dispatch(
    self,
    request: starlette.requests.Request,
    call_next
)
```

    
Add cache-control.

### LoggerMiddleware

```python3
class LoggerMiddleware(
    app: Callable[[MutableMapping[str, Any], Callable[[], Awaitable[MutableMapping[str, Any]]], Callable[[MutableMapping[str, Any]], Awaitable[NoneType]]], Awaitable[NoneType]],
    querystrings: bool = False,
    headers: bool = False
)
```

#### Ancestors (in MRO)

* starlette.middleware.base.BaseHTTPMiddleware

#### Methods

    
#### dispatch

```python3
def dispatch(
    self,
    request: starlette.requests.Request,
    call_next
)
```

    
Add logs.

### LowerCaseQueryStringMiddleware

```python3
class LowerCaseQueryStringMiddleware(
    app: Callable[[MutableMapping[str, Any], Callable[[], Awaitable[MutableMapping[str, Any]]], Callable[[MutableMapping[str, Any]], Awaitable[NoneType]]], Awaitable[NoneType]],
    dispatch: Union[Callable[[starlette.requests.Request, Callable[[starlette.requests.Request], Awaitable[starlette.responses.Response]]], Awaitable[starlette.responses.Response]], NoneType] = None
)
```

#### Ancestors (in MRO)

* starlette.middleware.base.BaseHTTPMiddleware

#### Methods

    
#### dispatch

```python3
def dispatch(
    self,
    request: starlette.requests.Request,
    call_next
)
```

    
dispatch request.

### TotalTimeMiddleware

```python3
class TotalTimeMiddleware(
    app: Callable[[MutableMapping[str, Any], Callable[[], Awaitable[MutableMapping[str, Any]]], Callable[[MutableMapping[str, Any]], Awaitable[NoneType]]], Awaitable[NoneType]],
    dispatch: Union[Callable[[starlette.requests.Request, Callable[[starlette.requests.Request], Awaitable[starlette.responses.Response]]], Awaitable[starlette.responses.Response]], NoneType] = None
)
```

#### Ancestors (in MRO)

* starlette.middleware.base.BaseHTTPMiddleware

#### Methods

    
#### dispatch

```python3
def dispatch(
    self,
    request: starlette.requests.Request,
    call_next
)
```

    
Add X-Process-Time.