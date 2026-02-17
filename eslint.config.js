import baseConfig from "./cfg/eslint.config.js";

export default [
  ...baseConfig,
  {
    files: ["init/*.yaml", "init/*.yml"],
    rules: {
      "yml/no-empty-document": "off",
      "yml/no-empty-mapping-value": "off",
    },
  },
];
