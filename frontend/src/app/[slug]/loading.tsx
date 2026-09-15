import { Container } from "@/components/ui/Container";

export default function CustomerLoading() {
  return (
    <main className="flex flex-1 flex-col items-center justify-center">
      <Container className="flex flex-col items-center gap-3">
        <div className="h-8 w-8 animate-pulse rounded-full bg-surface-sunken" />
        <div className="h-4 w-40 animate-pulse rounded-full bg-surface-sunken" />
      </Container>
    </main>
  );
}
