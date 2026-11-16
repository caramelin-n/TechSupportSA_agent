import { BrowserRouter, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./auth/AuthContext";
import AppLayout from "./components/AppLayout";
import RequireAuth from "./components/RequireAuth";
import ChatPage from "./pages/ChatPage";
import LoginPage from "./pages/LoginPage";
import NewTicketPage from "./pages/NewTicketPage";
import NotFoundPage from "./pages/NotFoundPage";
import TicketDetailPage from "./pages/TicketDetailPage";
import TicketsPage from "./pages/TicketsPage";

function protectedPage(page) {
  return <RequireAuth><AppLayout>{page}</AppLayout></RequireAuth>;
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/" element={protectedPage(<ChatPage />)} />
          <Route path="/tickets" element={protectedPage(<TicketsPage />)} />
          <Route path="/tickets/new" element={protectedPage(<NewTicketPage />)} />
          <Route path="/tickets/:ticketId" element={protectedPage(<TicketDetailPage />)} />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
