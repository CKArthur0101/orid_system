import { useFormStatus } from "react-dom";
import { Button } from "@/components/ui/button";

export function SubmitButton({ text, className }: { text: string; className?: string }) {
  const { pending } = useFormStatus();

  return (
    <Button
      className={className ?? "w-full"}
      variant={className ? "ghost" : "default"}
      type="submit"
      disabled={pending}
    >
      {pending ? "Loading..." : text}
    </Button>
  );
}
