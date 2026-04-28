# Interface specification

Reference: `concept.png`, generated with the built-in image tool for this project.

Primary surface: support inbox with fixed left navigation, a four-column summary band, status tabs and search, ticket queue, ticket detail, customer message, investigation timeline, and evidence panel. Secondary surfaces: evaluation report table, policy library, new-ticket dialog, reviewer approval and receipt states.

Tokens: cool gray background #f6f7f9; white surfaces; navy text #122343; muted text #6b7d9a; blue accent #075cf0; subtle separators #e6ebf2. Inter with system fallbacks. Seven-pixel panel radii, six-pixel controls, restrained badges. Lucide outline icons.

UI is all native HTML/React; the reference screenshot is not shipped as a fake interface. No decorative raster assets are needed. Mobile stacks the queue and detail, reduces panel columns, and exposes navigation through a toggle.

Functional deviations from generated reference: identity selector enables role testing; dates/counts come from actual data; unavailable product color is omitted; policy source counts replace nonfunctional 'View all'; static three-dot and empty activity dropdown controls are omitted; real approval, report, and error states extend the same visual system.

Concept prompt: Full desktop ResolveDesk ecommerce support workspace, cool gray/white/navy/cobalt, left navigation, three seeded tickets, selected damaged-headphones case, Start investigation, activity empty state and evidence panels; native code UI, no marketing hero or invented metrics.
