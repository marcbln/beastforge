# beastforge CLI cheat sheet

## Most useful

| Task | Command |
|------|---------|
| List creatures | `beastforge list` |
| List as JSON | `beastforge list --json` |
| Inspect parameters | `beastforge params {{name}}` |
| Generate a package | `beastforge render {{name}}` |
| Generate with an override | `beastforge render {{name}} --set {{key}}={{value}}` |
| Validate everything | `beastforge validate` |
| Validate one recipe | `beastforge validate {{name}}` |
| Compare showroom frames | `beastforge showroom` |
| Accept new references | `beastforge showroom --accept` |
| Print version | `beastforge version` |

## list

> Scan the in-repo library and print the catalog without generating anything.
> More information: `beastforge list --help`

| Task | Command |
|------|---------|
| List all creatures | `beastforge list` |
| Machine-readable catalog | `beastforge list --json` |
| Filter by category | `beastforge list --category {{category}}` |
| Filter by tag | `beastforge list --tag {{tag}}` |
| Combine tags (AND) | `beastforge list --tag {{tag}} --tag {{tag2}}` |
| Use another library | `beastforge list --library {{path}}` |

## params

> Show one recipe's declared parameters, defaults, units, and limits.
> More information: `beastforge params --help`

| Task | Command |
|------|---------|
| Show parameters | `beastforge params {{name}}` |
| Machine-readable knobs | `beastforge params {{name}} --json` |
| Inspect an explicit file | `beastforge params {{path}}` |

## render

> Generate one `.glb` plus its sidecar manifest, gated before commit.
> More information: `beastforge render --help`

| Task | Command |
|------|---------|
| Generate a library creature | `beastforge render {{name}}` |
| Choose the output directory | `beastforge render {{name}} -o {{dir}}` |
| Override a parameter | `beastforge render {{name}} --set {{key}}={{value}}` |
| Overwrite existing outputs | `beastforge render {{name}} --force` |
| Preview without writing | `beastforge render {{name}} --dry-run` |
| Machine-readable report | `beastforge render {{name}} --json` |
| Render an explicit recipe | `beastforge render {{path}}` |

## validate

> Run the single gate; exits non-zero on any error-severity finding.
> More information: `beastforge validate --help`

| Task | Command |
|------|---------|
| Validate the shipped library | `beastforge validate` |
| Validate one creature | `beastforge validate {{name}}` |
| Validate an explicit recipe | `beastforge validate {{path}}` |
| Machine-readable findings | `beastforge validate --json` |

## showroom

> Render turntable and extreme-bend frames and compare them to approved references.
> More information: `beastforge showroom --help`

| Task | Command |
|------|---------|
| Compare the whole library | `beastforge showroom` |
| Compare one creature | `beastforge showroom {{name}}` |
| Accept new references explicitly | `beastforge showroom --accept` |
| Machine-readable report | `beastforge showroom --json` |

## version

> Print `beastforge <semver>` and exit 0.
> More information: `beastforge version --help`

| Task | Command |
|------|---------|
| Print the version | `beastforge version` |
| Root version flag | `beastforge --version` |

## about

> Print name, version, purpose, maintainer, license, repository, and docs.
> More information: `beastforge about --help`

| Task | Command |
|------|---------|
| Show the about screen | `beastforge about` |
