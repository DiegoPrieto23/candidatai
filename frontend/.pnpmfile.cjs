// openapi-typescript (lo usa `pnpm gen:api`) necesita el API de JavaScript de TypeScript, que
// TypeScript 7 ya no tiene. Pide TypeScript como dependencia ?peer?, as? que tomar?a la 7 del
// proyecto: se le da la 6 como dependencia propia. El resto sigue con la 7.
module.exports = {
  hooks: {
    readPackage(pkg) {
      if (pkg.name === "openapi-typescript") {
        if (pkg.peerDependencies) delete pkg.peerDependencies.typescript;
        pkg.dependencies = { ...pkg.dependencies, typescript: "6.0.3" };
      }
      return pkg;
    },
  },
};
