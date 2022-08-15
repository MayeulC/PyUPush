# Minimal D-Bus UnifiedPush implementation in Python

# Note: early WIP

## Goals
* Implement the [D-Bus specification](https://unifiedpush.org/spec/server/) of UnifiedPush in a server and distributor
* Implement sample users of that client and server
* Provide an example implementation that can be studied and modified easily, both for future UnifiedPush implementers, and for application developers
* Keep everything short (not terse) and readable, with enough comments
* Provide a platform for benchmarking energy-efficiency of various push transports

## Non-goals
* Public deployments: this is mostly for testing
* Absolute security, including against DDoS and malicious users
* A useful example app
* High-performance
* Scalability to more than 10 users

## Architecture

See [UnifiedPush/](UnifiedPush/) for the UnifiedPush-specific part ("*distributor*" in UnifiedPush parlance), and [Application/](Application/) for the application part. There are readmes in both folders.

If you want to develop or refine a distributor, you will probably be more interested in the first, if you want to integrate UP in your application, have a look at the second.
As an app developer, libraries exist to make implementing UnifiedPush easier, see [this existing Go and C api](https://unifiedpush.org/developers/go_c/).

### Usage
1. Run the server-side distributor from [UnifiedPush/server.py](UnifiedPush/server.py)
2. Run the client-side distributor from [UnifiedPush/server.py](UnifiedPush/distributor.py)
3. Run the client application from [Application/UpConnector.py](UnifiedPush/UpConnector.py)
4. Observe the endpoint returned from the client application, and send it some data with `curl -d 'some_data' 'http://endpoint'`

Python scripts can be ran with `python script.py`

## TODO
* Bug fixes, especially lock-ups, exception handling
* Support unregistration
* Add more fully-fledged example that directly send a call to /push
* Add client and server-side application
* Rewrite API to better separate the logical parts, currently it relies a lot on globals and most classes calling into most others due to last-minute hacks
* Separate the API into its own files? Not sure if that goes against the goals.
* Usage documentation
* Unit testing, probably one of the most useful features that could come out of this project
