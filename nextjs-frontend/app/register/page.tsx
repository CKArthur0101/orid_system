"use client";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

import { register } from "@/components/actions/register-action";
import { useActionState } from "react";
import { SubmitButton } from "@/components/ui/submitButton";
import Link from "next/link";
import { FieldError, FormError } from "@/components/ui/FormError";

export default function Page() {
  const [state, dispatch] = useActionState(register, undefined);

  return (
    <div className="flex h-screen w-full items-center justify-center bg-gray-50 dark:bg-gray-900 px-4">
      <form action={dispatch}>
        <Card className="w-full max-w-sm rounded-lg shadow-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800">
          <CardHeader className="text-center">
            <CardTitle className="text-2xl font-semibold text-gray-800 dark:text-white sm:text-3xl">
              註冊
            </CardTitle>
            <CardDescription className="text-base text-gray-600 dark:text-gray-400">
              請輸入帳號（可為學號）、顯示名稱與密碼。
            </CardDescription>
          </CardHeader>

          <CardContent className="grid gap-6 p-6">
            <div className="grid gap-3">
              <Label
                htmlFor="email"
                className="text-gray-700 dark:text-gray-300"
              >
                帳號（學號）
              </Label>
              <Input
                id="email"
                name="email"
                type="text"
                autoComplete="username"
                placeholder="例如：114524020"
                required
                className="border-gray-300 dark:border-gray-600"
              />
              <FieldError state={state} field="email" />
            </div>

            <div className="grid gap-3">
              <Label
                htmlFor="display_name"
                className="text-gray-700 dark:text-gray-300"
              >
                顯示名稱（選填）
              </Label>
              <Input
                id="display_name"
                name="display_name"
                type="text"
                placeholder="例如：邱振凱（登入後顯示為「邱振凱 同學」）"
                className="border-gray-300 dark:border-gray-600"
              />
              <FieldError state={state} field="display_name" />
            </div>

            <div className="grid gap-3">
              <Label
                htmlFor="password"
                className="text-gray-700 dark:text-gray-300"
              >
                密碼
              </Label>
              <Input
                id="password"
                name="password"
                type="password"
                required
                className="border-gray-300 dark:border-gray-600"
              />
              <FieldError state={state} field="password" />
            </div>

            <SubmitButton text="建立帳號" />
            <FormError state={state} />

            <div className="mt-4 text-center text-base text-gray-600 dark:text-gray-400">
              已經有帳號了嗎？{" "}
              <Link
                href="/login"
                className="text-blue-500 hover:text-blue-600 dark:text-blue-400 dark:hover:text-blue-500"
              >
                回登入
              </Link>
            </div>
          </CardContent>
        </Card>
      </form>
    </div>
  );
}
