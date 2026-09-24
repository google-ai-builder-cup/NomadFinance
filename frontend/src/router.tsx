import { createBrowserRouter } from "react-router-dom";

import App from "@/App";

// Single placeholder route proving React Router is wired end to end. The real
// route tree (app shell, pillar pages, protected routes) lands with NF-P1-010.
export const router = createBrowserRouter([
  {
    path: "/",
    element: <App />,
  },
]);
