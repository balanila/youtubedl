# Validation

- After editing source files, run IntelliJ inspections with warnings included when the IDE tools are available. Fix warnings introduced by the changes before completing the task.
- Verify HTML asset paths both against the repository layout and the application's HTTP routes.
- Give form inputs accessible labels. Handle expected HTTP failures directly rather than throwing exceptions that are caught in the same block.
- Validate GitHub Actions YAML and the syntax of embedded shell scripts after workflow edits.
- Do not suppress inspections to conceal a problem. Report any remaining issues and checks that could not be run.
