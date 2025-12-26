export const metadata = {
  title: "Assistant Messages",
  description: "Next.js client for the Django assistant API"
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body
        style={{
          margin: 0,
          minHeight: "100vh",
          backgroundColor: "#f3f4f6"
        }}
      >
        {children}
      </body>
    </html>
  );
}


