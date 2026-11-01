"use client";

import type { ComponentPropsWithRef } from "react";
import { useRouter } from "next/navigation";

import { ButtonLink, type ButtonLinkProps } from "@/components/ui/Button";

import { navigateToFreshImport } from "./import-navigation";

type FreshImportLinkProps = Omit<ButtonLinkProps, "href"> &
  Pick<ComponentPropsWithRef<"a">, "onClick">;

/** Link to the import screen with a remount key so stale import state is not restored. */
export function FreshImportLink({
  onClick,
  ...rest
}: FreshImportLinkProps) {
  const router = useRouter();

  return (
    <ButtonLink
      href="/"
      {...rest}
      onClick={(event) => {
        event.preventDefault();
        navigateToFreshImport(router.push);
        onClick?.(event);
      }}
    />
  );
}
