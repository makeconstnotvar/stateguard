export default [
  {
    files: ["server/**/*.js", "client/**/*.js", "tests/**/*.js"],
    languageOptions: {
      ecmaVersion: "latest",
      sourceType: "module",
    },
    rules: {
      "no-unused-vars": "error",
      "no-undef": "error",
    },
  },
];
