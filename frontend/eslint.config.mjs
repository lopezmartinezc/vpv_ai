import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  {
    rules: {
      // A `const` read above its declaration throws a ReferenceError at
      // runtime, and TypeScript does not flag it when the read sits inside a
      // closure — even one an array method calls immediately. That shipped a
      // white screen once; this catches it in CI instead.
      "@typescript-eslint/no-use-before-define": [
        "error",
        {
          variables: true,
          functions: false,
          classes: false,
          enums: false,
          typedefs: false,
          ignoreTypeReferences: true,
        },
      ],
    },
  },
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
]);

export default eslintConfig;
