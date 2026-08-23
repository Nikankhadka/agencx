import { redirect } from "next/navigation";

/**
 * The apex is the owner's way in. Login-in-chat (O-2) replaced the marketing
 * landing, so `/` has nothing of its own to render and sends the owner to the
 * login thread.
 *
 * This replaces the rewrite the host-based proxy used to do (D22). It has to
 * be a real route: `/` is the one path the `[slug]` segment cannot catch, so
 * without a page here the apex would 404.
 */
export default function Root() {
  redirect("/login");
}
