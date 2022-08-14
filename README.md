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


