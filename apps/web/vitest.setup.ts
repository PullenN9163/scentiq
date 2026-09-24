import "@testing-library/jest-dom/vitest";

import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// Testing Library only registers its own cleanup when Vitest globals are
// enabled, and this project does not enable them. Without this, rendered DOM
// accumulates across tests in a file and queries match earlier renders.
afterEach(cleanup);
