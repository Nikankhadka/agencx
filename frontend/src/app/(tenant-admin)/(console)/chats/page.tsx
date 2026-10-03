import { EmptyState } from "@/components/ui/EmptyState";

/**
 * RF-15: the desktop empty pane. At `/chats` the thread side of the split has
 * no conversation yet, so it holds the "select a conversation" placeholder
 * instead of a blank column. It is only ever visible at `lg+` - the layout's
 * thread pane is `hidden` below `lg` - so a phone still lands on the list.
 *
 * Plain component, no `"use client"`: it is only static markup passed as
 * children to the client layout, and `EmptyState` takes only props.
 */
export default function ChatsPage() {
  return (
    <div data-testid="chats-empty-pane" className="flex h-full items-center justify-center">
      <EmptyState
        icon="forum"
        title="Select a conversation."
        description="Choose a conversation from the list to read and reply."
      />
    </div>
  );
}
