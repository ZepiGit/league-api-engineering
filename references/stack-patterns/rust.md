# Rust production patterns

Use these patterns for League adapters that run in a desktop process or service. Keep remote Riot traffic and loopback game-client traffic in separate clients.

## Typed failures and source provenance

```rust
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ErrorClass {
    Offline,
    Unauthorized,
    RateLimited,
    NotFound,
    NoData,
    UnsupportedContext,
    Transport,
    HttpStatus,
    Parse,
    SchemaDrift,
    PolicyBlocked,
}

#[derive(Debug)]
pub struct AdapterError {
    pub class: ErrorClass,
    pub status: Option<u16>,
    pub retry_after_seconds: Option<u64>,
    pub detail: String,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum EvidenceClass {
    VerifiedCurrent,
    ObservedUndocumented,
    Historical,
    Inference,
}

#[derive(Debug, Clone)]
pub struct Provenance {
    pub source_id: &'static str,
    pub endpoint_family: &'static str,
    pub evidence: EvidenceClass,
    pub observed_at_unix_seconds: u64,
    pub patch: Option<String>,
    pub population: Option<String>,
}

#[derive(Debug, Clone)]
pub struct Sourced<T> {
    pub value: T,
    pub provenance: Provenance,
}
```

Map local client absence to `Offline`, an authenticated Riot Web `401` or `403` to `Unauthorized`, and a valid empty result to `NoData`. Do not erase `population`: aggregate build statistics from different regions, ranks, patches, or sample windows are not interchangeable.

## Loopback TLS isolation

The League client may expose a loopback endpoint using a self-signed certificate. Construct that client from validated loopback connection metadata only. A remote client uses platform TLS validation and cannot accept a loopback connector.

```rust
use std::net::IpAddr;

pub struct LoopbackEndpoint {
    pub host: IpAddr,
    pub port: u16,
    pub password: String,
}

impl LoopbackEndpoint {
    pub fn new(host: IpAddr, port: u16, password: String) -> Result<Self, AdapterError> {
        if !host.is_loopback() {
            return Err(AdapterError {
                class: ErrorClass::PolicyBlocked,
                status: None,
                retry_after_seconds: None,
                detail: "certificate relaxation is limited to loopback".into(),
            });
        }
        Ok(Self { host, port, password })
    }
}

pub trait RemoteHttp {
    fn get(&self, url: &str, bearer_token: &str) -> Result<String, AdapterError>;
}

pub trait LoopbackHttp {
    fn get(&self, endpoint: &LoopbackEndpoint, path: &str) -> Result<String, AdapterError>;
}
```

The `LoopbackHttp` implementation may use a loopback-only certificate exception after checking `host.is_loopback()`. `RemoteHttp` always verifies certificates and never receives an LCU password. Keep the password in memory only; redact authorization headers and query strings from logs.

## Routing and authentication are distinct

```rust
#[derive(Debug, Clone, Copy)]
pub enum PlatformRoute { Na1, Euw1, Kr }

#[derive(Debug, Clone, Copy)]
pub enum RegionalRoute { Americas, Europe, Asia, Sea }

pub fn match_v5_route(platform: PlatformRoute) -> RegionalRoute {
    match platform {
        PlatformRoute::Na1 => RegionalRoute::Americas,
        PlatformRoute::Euw1 => RegionalRoute::Europe,
        PlatformRoute::Kr => RegionalRoute::Asia,
    }
}

pub fn match_url(route: RegionalRoute, puuid: &str) -> String {
    let host = match route {
        RegionalRoute::Americas => "americas.api.riotgames.com",
        RegionalRoute::Europe => "europe.api.riotgames.com",
        RegionalRoute::Asia => "asia.api.riotgames.com",
        RegionalRoute::Sea => "sea.api.riotgames.com",
    };
    format!("https://{host}/lol/match/v5/matches/by-puuid/{puuid}/ids")
}
```

Resolve platform-to-regional routing before building a request. Inject an authorized server-side credential at the trusted boundary; a desktop binary must not contain a production Riot key. Routing values are inputs independent of authentication.

## Bounded retry and cache identity

```rust
#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub struct CacheKey {
    pub source_id: &'static str,
    pub endpoint_family: &'static str,
    pub subject_id: String,
    pub patch: Option<String>,
    pub locale: Option<String>,
    pub region: Option<String>,
    pub queue: Option<String>,
    pub lane: Option<String>,
    pub tier: Option<String>,
}

pub fn retry_delay_seconds(error: &AdapterError, attempt: u8) -> Option<u64> {
    if attempt >= 3 { return None; }
    match error.class {
        ErrorClass::Offline | ErrorClass::Transport => Some(1_u64 << attempt),
        ErrorClass::RateLimited => error.retry_after_seconds.or(Some(2_u64 << attempt)),
        ErrorClass::HttpStatus if matches!(error.status, Some(500..=599)) => Some(1_u64 << attempt),
        _ => None,
    }
}
```

Retry only transient classes and stop after the bounded attempt count. Never retry `Unauthorized`, `Parse`, `SchemaDrift`, `PolicyBlocked`, `UnsupportedContext`, or ordinary `NoData`. Cache keys include every dimension that changes a response; static data includes patch and locale, while build statistics include population dimensions such as region, tier, lane, queue, patch, and sample window.

## Fixtures and optional canaries

```rust
#[derive(serde::Deserialize)]
struct ChampionFixture { id: String, name: String }

fn parse_champion_fixture(input: &str) -> Result<ChampionFixture, AdapterError> {
    serde_json::from_str(input).map_err(|error| AdapterError {
        class: ErrorClass::Parse,
        status: None,
        retry_after_seconds: None,
        detail: error.to_string(),
    })
}

#[test]
fn parses_sanitized_fixture() {
    let parsed = parse_champion_fixture(r#"{"id":"Aatrox","name":"Aatrox"}"#).unwrap();
    assert_eq!(parsed.id, "Aatrox");
}
```

Fixture tests use sanitized static payloads with no credentials, account identifiers, or real match histories. A network canary is optional and ignored by default; it runs only when explicitly enabled, reads no user data, and reports `SchemaDrift` when a documented shape changes instead of normalizing unknown fields silently.

```rust
#[test]
#[ignore = "optional network canary; requires explicit operator enablement"]
fn static_data_canary() {
    let version_input = std::env::var("CANARY_DDRAGON_VERSION").expect("explicit canary input");
    assert!(!version_input.is_empty());
}
```
