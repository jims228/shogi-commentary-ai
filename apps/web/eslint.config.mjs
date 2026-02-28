import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
  // Training/Lesson authoring area: relax a few rules to keep iteration fast.
  // NOTE: We intentionally scope this to training/lessons only.
  {
    files: [
      "src/lessons/**/*.{ts,tsx}",
      "src/lib/training/**/*.{ts,tsx}",
      "src/components/training/lesson/**/*.{ts,tsx}",
      "src/app/training/tesuji/**/*.{ts,tsx}",
      "src/app/training/castle/**/*.{ts,tsx}",
      "src/app/training/opening/**/*.{ts,tsx}",
    ],
    rules: {
      "@typescript-eslint/no-explicit-any": "off",
      "react-hooks/set-state-in-effect": "off",
      "@typescript-eslint/ban-ts-comment": "off",
      "prefer-const": "off",
    },
  },
]);

export default eslintConfig;
