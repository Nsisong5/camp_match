# Architecture State: Admin & Operations
- First module that exclusively coordinates and aggregates across other modules via public inbound ports/adapters without owning domain data other than audit trails and support issues.
- Strict request-before-outcome audit logging with uncertain action detection.
- Complete separation of concerns: domain logic framework-free, adapters isolated.
