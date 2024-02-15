import { FlatCompat } from "@eslint/eslintrc";
import js from "@eslint/js";
import arrayFunc from "eslint-plugin-array-func";
// import plugin broken for flag config
// https://github.com/import-js/eslint-plugin-import/issues/2556
//import importPlugin from "eslint-plugin-import";
import eslintPluginPrettierRecommended from "eslint-plugin-prettier/recommended";
import pluginSecurity from "eslint-plugin-security";
import eslintPluginUnicorn from "eslint-plugin-unicorn";
import globals from "globals";

const compat = new FlatCompat();

export default [
  {
    languageOptions: {
      globals: {
        ...globals.node,
      },
    },
    linterOptions: {
      reportUnusedDisableDirectives: "warn",
    },
    plugins: {
      // import: importPlugin,
      unicorn: eslintPluginUnicorn,
    },
    rules: {
      "max-params": ["warn", 4],
      "no-console": process.env.NODE_ENV === "production" ? "warn" : "off",
      "no-debugger": process.env.NODE_ENV === "production" ? "warn" : "off",
      "prettier/prettier": "warn",
      "security/detect-object-injection": "off",
      "space-before-function-paren": "off",
      "unicorn/prevent-abbreviations": "off",
      "unicorn/filename-case": [
        "error",
        { case: "kebabCase", ignore: [".*.md"] },
      ],
      /*
      ...importPlugin.configs["recommended"].rules,
      "import/no-unresolved": [
        "error",
        {
          ignore: ["^[@]"],
        },
      ],
      */
    },
    /*
    settings: {
      "import/parsers": {
        espree: [".js", ".cjs", ".mjs", ".jsx"],
        "@typescript-eslint/parser": [".ts"],
      },
      "import/resolver": {
        typescript: true,
        node: true,
      },
    },
    */
  },
  js.configs.recommended,
  arrayFunc.configs.all,
  pluginSecurity.configs.recommended,
  eslintPluginPrettierRecommended,
  ...compat.config({
    ignorePatterns: [
      "*~",
      "**/__pycache__",
      ".git",
      "!.circleci",
      ".mypy_cache",
      ".pytest_cache",
      ".ruff_cache",
      ".venv",
      "dist",
      "node_modules",
      "package-lock.json",
      "test-results",
      "typings",
    ],
    root: true,
    env: {
      node: true,
      es2024: true,
    },
    parserOptions: {
      ecmaFeatures: {
        impliedStrict: true,
      },
      ecmaVersion: "latest",
    },
    plugins: [
      "eslint-comments",
      //"import",
      "markdown",
      "no-constructor-bind",
      "no-secrets",
      "no-unsanitized",
      "no-use-extend-native",
      "optimize-regex",
      "promise",
      "simple-import-sort",
      "sonarjs",
      "switch-case",
    ],
    extends: [
      // CODE QUALITY
      "plugin:sonarjs/recommended",
      // LANGS
      "plugin:jsonc/recommended-with-jsonc",
      "plugin:markdown/recommended",
      "plugin:toml/recommended",
      "plugin:yml/standard",
      "plugin:yml/prettier",
      // PRACTICES
      "plugin:eslint-comments/recommended",
      //"plugin:import/recommended",
      "plugin:no-use-extend-native/recommended",
      "plugin:optimize-regex/all",
      "plugin:promise/recommended",
      "plugin:switch-case/recommended",
      // SECURITY
      "plugin:no-unsanitized/DOM",
    ],
    rules: {
      "eslint-comments/no-unused-disable": 1,
      "no-constructor-bind/no-constructor-bind": "error",
      "no-constructor-bind/no-constructor-state": "error",
      "no-secrets/no-secrets": "error",
      "simple-import-sort/exports": "warn",
      "simple-import-sort/imports": "warn",
      "switch-case/newline-between-switch-case": "off", // Malfunctioning
    },
    overrides: [
      {
        files: ["**/*.md"],
        processor: "markdown/markdown",
        rules: {
          "prettier/prettier": ["error", { parser: "markdown" }],
        },
      },
      {
        files: ["**/*.md/*.js"], // Will match js code inside *.md files
        rules: {
          "no-unused-vars": "off",
          "no-undef": "off",
        },
      },
      {
        files: ["**/*.md/*.sh"],
        rules: {
          "prettier/prettier": ["error", { parser: "sh" }],
        },
      },
      {
        files: ["*.yaml", "*.yml"],
        //parser: "yaml-eslint-parser",
        rules: {
          "unicorn/filename-case": "off",
        },
      },
      {
        files: ["*.toml"],
        //parser: "toml-eslint-parser",
        rules: {
          "prettier/prettier": ["error", { parser: "toml" }],
        },
      },
      {
        files: ["*.json", "*.json5", "*.jsonc"],
        //parser: "jsonc-eslint-parser",
      },
    ],
  }),
];
