module.exports = {
  root: true,
  env: {
    node: true,
    es2021: true,
  },
  extends: [
    "eslint:recommended",
    // LANGS
    "plugin:json/recommended",
    "plugin:markdown/recommended",
    //"plugin:md/recommended",
    "plugin:yaml/recommended",
    // PRETTIER
    "plugin:prettier/recommended",
  ],
  parserOptions: {
    ecmaFeatures: {
      impliedStrict: true,
    },
    ecmaVersion: 2022,
  },
  overrides: [
    {
      files: ["*.md"],
      parser: "markdown-eslint-parser",
      rules: {
        "prettier/prettier": ["error", { parser: "markdown" }],
      },
    },
    {
      files: ["*.md.js"], // Will match js code inside *.md files
      rules: {
        // disable 2 core eslint rules 'no-unused-vars' and 'no-undef'
        "no-unused-vars": "off",
        "no-undef": "off",
      },
    },
  ],
  plugins: [
    "eslint-comments",
    "json",
    "markdown",
    //"md",
    "prettier",
    "yaml",
  ],
  rules: {
    "max-params": ["warn", 4],
    /*
     md/remark plugins can't be read by eslint
     https://github.com/standard-things/esm/issues/855
    "md/remark": [ "error",
      {
        plugins: [
          "gfm",
          "preset-lint-consistent",
          "preset-lint-markdown-style-guide",
          "preset-lint-recommended",
          "preset-prettier"
        ],
      }
    ],
    */
    "prettier/prettier": "warn",
  },
  ignorePatterns: [
    "*~",
    "**/__pycache__",
    ".git",
    "!.circleci",
    ".mypy_cache",
    ".pytest_cache",
    ".venv",
    "dist",
    "node_modules",
    "test_results",
    "typings",
  ],
};
