# Parser cleanup

The current library parses comma-separated integers and preserves duplicates.
Consumers depend on the same order and error behavior. We want a plan to extract
the parser, add a CLI consumer, and write documentation. Parser extraction must
precede the CLI change; documentation can be independent. This is plan-only.
