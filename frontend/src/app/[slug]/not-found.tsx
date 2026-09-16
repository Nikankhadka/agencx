import { Container } from "@/components/ui/Container";

export default function CustomerNotFound() {
  return (
    <main className="flex flex-1 flex-col items-center justify-center">
      <Container className="flex flex-col items-center gap-2 text-center">
        <h1 className="text-title-2 font-semibold text-text">There&apos;s no business here.</h1>
      </Container>
    </main>
  );
}
