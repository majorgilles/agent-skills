---
name: trace-flow
description: Trace an architectural flow hop by hop, with the trigger of every hop proven in code. Use when the user asks how something flows through the system, what triggers a step, which function, worker, cron, signal or event runs next, or where a change sits in a pipeline.
---

# Trace a flow

A flow is a chain of **hops**. A hop is one invocation of a deployable unit: a serverless function, a queue worker, a container handling a request, an admin action. Its **handler** is the entry point. Everything that runs inside that process (dependency wiring, application service, repositories, aggregates, ORM signals, after-commit hooks) is an **internal step** of the hop, not a hop of its own.

A new hop starts only where work crosses a **process boundary**: an event on a topic, a command on a queue, a schedule, an HTTP call to another service. The reader must see, for every hop, exactly what starts it.

A hop's **trigger** has two halves, and both need a `file:line`:

- **Emitter**: the code in the previous hop that publishes the event or command.
- **Route**: what carries it into this hop. Usually an infrastructure-as-code declaration (CDK, Terraform, Serverless, Kubernetes, a framework's routing table) that binds a topic subscription, a queue event source, a schedule or a URL to this handler, with its filter policy.

A hop with only one half proven is **UNVERIFIED**. Say so in the output; a subscription with no proven emitter is a guess, not a trigger.

## Before you start

Read the project's own architecture notes (`CLAUDE.md`, `AGENTS.md`, ADRs, a `docs/` architecture page). Learn three things from them, or from the code when they are silent:

- how a message is published, and how the publisher decides its channel;
- where the infrastructure code declares subscriptions, queues and schedules;
- the names the project uses for its building blocks.

## Steps

1. **Bound the flow.** Name the start (a user action, a cron, an incoming webhook) and the end (the state the user asked about). Done when both ends are one sentence each.
2. **Find the fan-in.** A flow rarely has one start. Take the first command or application service of the flow and search the **whole repository** for every caller of it and of its factory, then classify each caller by entry point kind (see below). Done when every caller is listed with its `file:line` and kind.
3. **Walk forward one hop at a time.** For each hop, find the handler, then prove its trigger: search for the emitter, then the route that delivers it. Done when the hop has handler, emitter and route, each with `file:line`, or is marked UNVERIFIED with what is missing.
4. **Walk the internal steps in building blocks.** Follow the handler into the code it delegates to, and name each step by its building block (see below). Done when every write and every emit of the hop has a `file:line` and a building block.
5. **Record the deciding state.** For each hop, name the data that decides its outcome (which repository read, which filter, which aggregate field, which business rule). Done when every hop lists what it reads and what it changes.
6. **Find the fan-out.** One event often reaches several consumers. List every subscriber of each event in the flow, including the ones off the path the user asked about. Done when each message names all of its routes.
7. **Check every hop block** against the rules below, and fix or mark what fails. Done when every hop passes all four.
8. **Write the output** below.

## Hop block rules

Every hop block carries these fields, in this order, every time:

1. **Trigger** names the message kind and exact type: `[event] ORDER_PLACED`, `[command] ReserveStockCommand`, or `schedule`.
2. **emitter** and **route** each sit on their own line with a `file:line`. The emitter line opens with the hop that sent the message, by number and name (`emitter: ← ① CHECKOUT, orders/service.py:88`), so the reader can navigate back. An emitter outside the flow names its entry point instead (`← entry point: admin action`). When several hops emit the same type, list one emitter line per hop. When one half is not found, the line reads `emitter: UNVERIFIED (searched: …)` and the hop goes into the Unverified list.
3. **Emits** lists every message the hop publishes, success and failure paths both, each with its kind, exact type, `file:line`, channel and next hop. A hop that publishes nothing says `Emits: none`.
4. **The channel comes from the publisher, not from a name.** Read how the publisher picks the topic or queue (a base class, a mapping, a config key) and quote the line that proves it. A message named like a queue is not proof that it goes there.

## Entry point kinds

A flow can start from any of these; check each one in step 2:

- **Function or worker**: triggered by an event, a command or a schedule.
- **Admin action**: a back-office action or save button, run by an operator.
- **Agent or automation tool**: a tool called by an automation platform or an AI assistant.
- **API endpoint**: a REST route or GraphQL resolver.
- **ORM signal or model hook**: a save receiver that calls the service whenever any code path saves the model.
- **Another application service**: an in-process caller, whose own entry points then join the fan-in.
- **Script**: run by an engineer; list it, but mark it manual.

## Building blocks inside a hop

Name each internal step with the block it belongs to, in the project's own words where it has them:

- **Handler**: the entry function. Thin: it parses the message, builds the command, and calls the service. Logic found here is worth flagging.
- **Factory or wiring**: where adapters are chosen; read it to know which concrete adapter sits behind each port.
- **Application service**: one use case. It loads aggregates, calls domain logic, persists and publishes.
- **Command**: the imperative input of a service. 1:1 with its consumer.
- **Repository**: the persistence port and its implementation. Note which query a read uses, since filters there often decide the outcome.
- **Port**: an interface to an external system (a feature-flag client, a payment provider).
- **Aggregate**: the domain model whose behavior methods change state and stage events.
- **Domain service**: stateless domain logic.
- **Specification or rule**: a business rule; a status or validation outcome is usually decided here.
- **Event**: past tense (`ORDER_PLACED`), 1:N, published on a topic.
- **Legacy code**: code that predates the current layout; name it as it is.

## Where triggers hide

Process boundaries, which start a hop:

- **Event on a topic**: the publisher maps the event to a topic. The subscriber's filter policy decides which event types reach it; read the filter, not the handler's docstring.
- **Command on a queue**: the publisher maps the command to a queue, and an event source mapping binds the queue to its worker.
- **Schedule**: a cron or rate expression, often set per environment in configuration. Check every environment: a schedule can be off in one of them.
- **Topic to topic**: a consumer can republish what it receives, sometimes through a table and a save hook; follow the chain to the topic that the next hop reads.

Inside a hop, which only lead to an emit:

- **ORM signal or save hook**: a receiver and its watched fields, running in the same process as the save. A bulk update often skips signals, so a write path that uses one emits nothing.
- **After-commit hook**: the emit waits for the transaction, and a rollback emits nothing.
- **Test-time muting**: fixtures that mute signals or stub publishers make an emitter look absent in tests while it fires in production.

## Output

1. **Entry points.** A table of every entry point found in step 2: kind, `file:line`, and which hop of the flow it joins.
2. **Hop list.** One block per hop, in order. Internal steps are an indented, ordered list inside the block, each tagged with its building block:

   ```
   ① CHECKOUT — POST /orders (api/orders.py:40)
      Trigger: HTTP request from the web shop
        route:  router.post("/orders") (api/routes.py:12)
      Steps:
        1. [handler]     validate the cart and build PlaceOrderCommand
        2. [service]     PlaceOrderService.execute(PlaceOrderCommand) (orders/service.py:61)
        3. [repository]  OrderRepository.save → Order, status PLACED
      Emits:   [event] ORDER_PLACED, after commit (orders/service.py:88)
               → orders topic, because OrderPlaced extends DomainEvent (publisher.py:52) → ②

   ② RESERVE STOCK — reserve_stock worker (stock/worker.py)
      Trigger: [event] ORDER_PLACED
        emitter: ← ① CHECKOUT, orders/service.py:88 (after commit)
        route:   orders topic → subscription with filter type=ORDER_PLACED (infra/stock.ts:30)
      Steps:
        1. [handler]     load the order lines (worker.py:18)
        2. [service]     ReserveStockService.execute (stock/service.py:25)
                         reserves every line, or none when one is out of stock
      Emits:   [event] STOCK_RESERVED, on success (stock/service.py:47) → payments topic → ③
               [event] STOCK_SHORTAGE, when a line is out of stock (stock/service.py:52) → notify_customer worker
   ```

3. **Diagram.** One text diagram of the whole flow, one box per hop, with every entry point drawn where it joins. Label every arrow with its trigger (event or command, and its topic, queue or schedule), so no arrow is unexplained.
4. **Placement table.** When the user asks about a change or a component, a table: piece, hop, internal step, building block, what it does there.
5. **Unverified list.** Every hop or half-trigger not proven, with the search that failed.
