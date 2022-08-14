# Example Python implementation of a UnifiedPush D-Bus distributor and corresponding server

## Server

The server implements the [Server-Server part of the UnifiedPush specification](https://unifiedpush.org/spec/server/).

It also implements a simple protocol to communicate with the distributor application.

### UnifiedPush Specification

Endpoints:
* Once the distributor application gives you an endpoint URL, you can query it with an `HTTP GET` and get the following answer: `{"unifiedpush":{"version":1}}`
  * If you do not get the above answer, the endpoint you have is invalid.
* If the above endpoint is valid, you can `HTTP POST` some content to it, that will be forwarded to the distributor, and then to the connected app.

Example endpoint: `http://127.0.0.1:8976/push/id/WQVOXKBGG`

Example usage:
```bash
$ curl -v "http://127.0.0.1:8976/push/id/WQVOXKBGG" -d "Example payload"
```

### Server-Distributor protocol

**Note: This is not part of the UP specification, it is distributor-dependent**

* Register an application to get an id:
  * `HTTP GET /client/register`
  * Response: `{"id":"WQVOXKBGG"}` That string is the client id, the push url is constructed by appending it to `/push/id/`
* Listen to push messages for that id:
  * `HTTP GET /client/id/WQVOXKBGG`
  * The connection remains open while the client listens

<details><summary>Example from curl</summary>

#### Registration

```bash
$ curl -v "127.0.0.1:8976/client/register"
*   Trying 127.0.0.1:8976...
* Connected to 127.0.0.1 (127.0.0.1) port 8976 (#0)
> GET /client/register HTTP/1.1
> Host: 127.0.0.1:8976
> User-Agent: curl/7.84.0
> Accept: */*
> 
* Mark bundle as not supporting multiuse
* HTTP 1.0, assume close after body
< HTTP/1.0 200 OK
< Server: BaseHTTP/0.6 Python/3.10.5
< Date: Sun, 14 Aug 2022 18:28:14 GMT
< Content-type: text/json
< 
* Closing connection 0
{"id":"WQVOXKBGG"}%
```

#### Reception

```bash
$ curl -v "127.0.0.1:8976/client/id/WQVOXKBGG"
*   Trying 127.0.0.1:8976...
* Connected to 127.0.0.1 (127.0.0.1) port 8976 (#0)
> GET /client/id/WQVOXKBGG HTTP/1.1
> Host: 127.0.0.1:8976
> User-Agent: curl/7.84.0
> Accept: */*
> 
* Mark bundle as not supporting multiuse
* HTTP 1.0, assume close after body
< HTTP/1.0 200 OK
< Server: BaseHTTP/0.6 Python/3.10.5
< Date: Sun, 14 Aug 2022 17:39:27 GMT
< Content-type: text/plain
* HTTP/1.0 connection set to keep alive
< Connection: keep-alive
< 
Example payload

Example with another payload

Example with yet another payload
```

</details>


