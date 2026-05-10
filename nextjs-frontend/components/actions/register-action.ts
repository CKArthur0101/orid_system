"use server";

import { redirect } from "next/navigation";

import { registerRegister } from "@/app/clientService";

import { registerSchema } from "@/lib/definitions";
import { getErrorMessage } from "@/lib/utils";

export async function register(prevState: unknown, formData: FormData) {
  const validatedFields = registerSchema.safeParse({
    email: formData.get("email") as string,
    password: formData.get("password") as string,
    display_name: (formData.get("display_name") as string) || undefined,
  });

  if (!validatedFields.success) {
    return {
      errors: validatedFields.error.flatten().fieldErrors,
    };
  }

  const { email, password, display_name } = validatedFields.data;

  const input = {
    body: {
      email,
      password,
      ...(display_name ? { display_name } : {}),
    },
  };
  try {
    const { error } = await registerRegister(input);
    if (error) {
      return { server_validation_error: getErrorMessage(error) };
    }
  } catch (err) {
    console.error("Registration error:", err);
    return {
      server_error: "An unexpected error occurred. Please try again later.",
    };
  }
  redirect(`/login`);
}
