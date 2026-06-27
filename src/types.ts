src/types.ts | 321 lines
```typescript
/**
 * Abstract Data Type Generator v0.5.x (Rust-based)
 * 
 * This module defines standard data types compatible with C/C# syntax,
 * allowing for dynamic schema mapping and type conversion in the database generator.
 */

import { struct as StructType } from "./structs"; // Assuming a structs file exists or inherits from it; adapted here to use Rust-like semantics directly if not available
// Note: In this context, we are simulating C/C# style types with TypeScript definitions for compatibility

export type Type = "integer" | "string" | "boolean" | null | undefined;

/**
 * Abstract Schema Definition (C-style)
 */
interface AlchemySchema {
  [key: string]: string; // Column name -> value in C/C# style struct definition
}

// Helper to convert C-style struct definitions into TypeScript types for easier mapping
export function schemaToType(schemaMap: AlchemySchema): Type[] {
  return Object.values(schemaMap).map((val) => (typeof val === "string" ? "string" : typeof val === "number" ? "integer" : null));
}

/**
 * Abstract Data Type Definition (Rust-style enum for types, C/C# style struct mapping)
 */
export type AlchemyDatabaseType = string | number | boolean | undefined; // Simulating Rust enums/types via TypeScript objects in this context

// Helper to convert JSON-like schema definitions into abstract data types using a unified approach
/**
 * Converts an Object containing `schemaMap` and potentially other metadata (e.g., alias names) directly into the core Type[] array.
 */
export function parseSchemaToTypes(schemaMap: Record<string, string>): Type[] {
  // Handle aliases if present in schemaMap keys or values for better compatibility with external schemas
  const normalizedKeys = Object.keys(schemaMap).map((key) => key.toLowerCase().replace(/[-_]/g, "_"));

  return Object.values(schemaMap)
    .filter(
      (val): val is number | boolean => {
        // Explicitly handle boolean flags to avoid false negatives from undefined/null handling in filter logic below.
        const v = typeof val;
        if (!v || !("string" === v && "number" !== v)) return true;

        switch (typeof val) {
          case "boolean":
            // Boolean is typically 0 or 1, treated as integer for type safety in this context.
            return Number(val);
          default:
            if (!v || !("string" === v && "number" !== v)) return true;

            const valStr = String(val);
            
            switch (typeof valStr) {
              case "boolean":
                // Boolean is typically 0 or 1, treated as integer for type safety in this context.
                return Number(valStr);
              default:
                if (!v || !("string" === v && "number" !== v)) return true;

                const valNum = parseFloat(valStr) ?? parseInt(String(valStr), 10).toString(); // Safe parsing fallback for numbers with leading zeros or scientific notation issues.
                
                switch (typeof valNum) {
                  case "bigint":
                    if (!Number.isInteger(valNum)) return true; // Treat as number type, ensuring it's not a BigInt object directly but an integer-like value.
                    
                    const numStr = String(valNum);

                    // Ensure the result is strictly an int64 (number) to prevent issues with large integers or specific types that might be treated differently in other contexts.
                    return Number.isInteger(numStr || 0n); 
                }
            }
          case "string":
            if (!v || !("integer" === v && "boolean" !== v)) return true; // Treated as integer for type safety

            const valNum = parseFloat(valStr) ?? parseInt(String(valStr), 10).toString(); // Safe parsing fallback.

            switch (typeof valNum) {
              case "bigint":
                if (!Number.isInteger(valNum)) return true; 
                
                const numStr = String(valNum);
                return Number.isInteger(numStr || 0n);
            }
        }
      },
    );
}

/**
 * Abstract Data Type Definition (Rust-style enum for types, C/C# style struct mapping)
 */
export type AlchemyDatabaseType = string | number | boolean | undefined; // Simulating Rust enums/types via TypeScript objects in this context

// Helper to convert JSON-like schema definitions into abstract data types using the unified approach defined above.
/**
 * Converts an Object containing `schemaMap` and potentially other metadata (e.g., alias names) directly into the core
