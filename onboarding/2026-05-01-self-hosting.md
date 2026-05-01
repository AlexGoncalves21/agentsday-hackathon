# Self-Hosting

## Information

Self-hosting means running software or services on infrastructure you control instead of relying entirely on third-party SaaS providers. For personal infrastructure, this can mean a home server, VPS, NAS, rented bare-metal machine, private cloud instance, or local machine. Common self-hosted services include file sync, notes, password managers, media servers, RSS readers, calendars, Git hosting, dashboards, automation, monitoring, and AI tooling.

The main benefits are control, data ownership, customization, privacy, resilience against platform changes, and learning. Self-hosting can make a person less dependent on closed platforms and recurring SaaS pricing. It also makes the system more inspectable and portable, especially when storage is file-first and based on open formats like Markdown.

The main downside is operational responsibility. A self-hosted service needs updates, backups, security patches, uptime monitoring, network configuration, TLS, authentication, permissions, disk management, and disaster recovery. A badly maintained self-hosted service can be less private and less secure than a well-run hosted service. Self-hosting is not automatically better; it trades vendor dependence for maintenance burden.

In programming language history, self-hosting has another meaning: a compiler or toolchain capable of building itself. That sense is conceptually useful here too. A second brain system could eventually become self-improving or self-maintaining, but that only becomes safe if it has clear boundaries, tests, and recovery paths.

For this project, self-hosting is relevant because a Markdown second brain is naturally portable. The `input/`, `brain/`, and `runs/` folders can live in Git, sync across machines, or be served locally. A Telegram ingestion agent and wiki compiler can run locally through a Cloudflare Tunnel during development, then move to a VPS or home server later.

Important related concepts:

- digital sovereignty
- personal infrastructure
- data ownership
- local-first software
- backups
- operational burden
- observability
- threat modeling
- private AI
- edge AI

## Sources

- https://www.privacyguides.org/en/self-hosting/
- https://doc.yunohost.org/oc/admin/about_self_hosting/
- https://en.wikipedia.org/wiki/Self-hosting_%28network%29
- https://en.wikipedia.org/wiki/Self-hosting_%28compilers%29

