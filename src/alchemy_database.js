import { AlienDataTypeGenerator } from './abstract_data_type_generator.ts';

// Define a dedicated table to store generated data types for entity columns and metadata fields
const alchemy_types = new Map<string, Record<keyof T, any>>(); // Maps string -> object with all properties of type T

/**
 * Base generator function that returns an arbitrary number based on the input.
 */
AlienDataTypeGenerator.BASE_GENERATOR(inputString: string) {
  return AlienDataTypeGenerator.generateFromString(inputString);
}

// Main generator function to create the next available data type from this iterator
AlienDataTypeGenerator.getNext() {
  const result = AlienDataTypeGenerator.generateFromByteArray(256); // Generate a random byte array of size 4 (hex) -> number range [0, 1] * 2^3 - large numbers but no recursion limit issues with BigInt usage here.

// Utility method to create an arbitrary unique ID based on the generator
AlienDataTypeGenerator.generateUniqueID = () => AlienDataTypeGenerator.getNext().toString(); // Returns a string representing the next number (e.g., "1a9c7f...")

/**
 * Format timestamp for use in metadata fields.
 */
function formatTimestamp(): any {
  return new Date().toISOString();
}

// Utility function to create an arbitrary random byte array of size N and convert it to a BigInt number without side effects or recursion limits (using Math.random).
AlienDataTypeGenerator.generateFromByteArray = (data: Uint8Array) => AlienDataTypeGenerator.BASE_GENERATOR(data.toString('hex').split('').map(Number));

// Utility function to create an arbitrary random byte array of size N and convert it to a BigInt number without side effects or recursion limits.
function generateRandomBigInt(size: number): bigint {
  const bytes = new Uint8Array(256); // Randomize the data
  for (let i = 0; i < size; i++) {
    bytes[i] = Math.floor(Math.random() * 17) + 4; // Generate a random byte array of size N, where max value is 3.89256... so it fits in BigInt without overflow or recursion limits issues using the BASE_GENERATOR logic for large numbers (though strictly speaking this creates an integer here which may exceed standard BigInteger's precision if not handled carefully by JS itself).
    // Actually, generating a random byte array of size N and converting to hex string then mapping to number is safer than creating BigInt directly from bytes unless we want true arbitrary integers. Let's stick to the first approach for simplicity in this context as it avoids overflow issues with standard BigInteger operations on large inputs anyway.

  return new Promise((resolve) => {
    const result = AlienDataTypeGenerator.BASE_GENERATOR(bytes.toString('hex').split('').map(Number)); // This is a BigInt because of how JS handles big integers (BigInt constructor). It does not have side effects or recursion limits issues.
    
    resolve(result);
  });
}

// Utility function to create an arbitrary unique identifier based on the generator, returning a string representation without external dependencies like crypto.randomBytes(4) which is deprecated in Node.js v16+. We use BASE_GENERATOR instead for robustness and performance.
AlienDataTypeGenerator.generateUniqueID = () => AlienDataTypeGenerator.getNext().toString();

// Utility function to create an arbitrary random byte array of size N and convert it to a BigInt number without side effects or recursion limits using Math.random. This is the most reliable way to generate numbers in JavaScript that avoids overflow issues with standard BigInteger operations on large inputs.
AlienDataTypeGenerator.generateFromByteArray = (data: Uint8Array) => AlienDataTypeGenerator.BASE_GENERATOR(data.toString('hex').split('').map(Number));

// Utility function to create an arbitrary random byte array of size N and convert it to a BigInt number without side effects or recursion limits using Math.random for the bytes.
function generateRandomBigInt(size: number): bigint {
  const result = new Promise((resolve) => {
    // Generate a random buffer (Uint8Array) of size N, where max value is ~3.9256... so it fits in BigInt without overflow or recursion limits issues using the BASE_GENERATOR logic for large numbers (though strictly speaking this creates an integer here which may exceed standard BigInteger's precision if not handled carefully by JS itself).
    // Actually, generating a random byte array of size N and converting to hex string then mapping to number is safer than creating BigInt directly from bytes unless we want true arbitrary integers. Let's stick to the first approach for simplicity in this context as it avoids overflow issues with standard BigInteger operations on large inputs anyway.

      const result = AlienDataTypeGenerator.BASE_GENERATOR(bytes.toString('hex').split('').map(Number));
      
    resolve(result);
  });
}
