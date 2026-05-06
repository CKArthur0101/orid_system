"use client";

import { useActionState } from "react";
import { notFound, useSearchParams } from "next/navigation";
import { passwordResetConfirm } from "@/components/actions/password-reset-action";
import { SubmitButton } from "@/components/ui/submitButton";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Suspense } from "react";
import { FieldError, FormError } from "@/components/ui/FormError";

function ResetPasswordForm() {
  const [state, dispatch] = useActionState(passwordResetConfirm, undefined);
  const searchParams = useSearchParams();
  const token = searchParams.get("token");

  if (!token) notFound();

  return (
    <form action={dispatch}>
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle className="text-2xl sm:text-3xl">重設密碼</CardTitle>
          <CardDescription className="text-base">請輸入新密碼，並再次確認。</CardDescription>
        </CardHeader>

        <CardContent className="grid gap-4">
          <div className="grid gap-2">
            <Label htmlFor="password">新密碼</Label>
            <Input id="password" name="password" type="password" required />
          </div>
          <FieldError state={state} field="password" />

          <div className="grid gap-2">
            <Label htmlFor="passwordConfirm">確認新密碼</Label>
            <Input
              id="passwordConfirm"
              name="passwordConfirm"
              type="password"
              required
            />
          </div>
          <FieldError state={state} field="passwordConfirm" />

          <input
            type="hidden"
            id="resetToken"
            name="resetToken"
            value={token}
            readOnly
          />

          <SubmitButton text="確認重設" />
          <FormError state={state} />
        </CardContent>
      </Card>
    </form>
  );
}

export default function Page() {
  return (
    <div className="flex h-screen w-full items-center justify-center px-4">
      <Suspense fallback={<div>載入中…</div>}>
        <ResetPasswordForm />
      </Suspense>
    </div>
  );
}
