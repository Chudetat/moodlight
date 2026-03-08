"use client";

import { useState } from "react";
import { useAuth } from "@/lib/hooks/use-auth";
import {
  useUserTeam,
  useTeamMembers,
  useTeamWatchlists,
  useInviteTeamMember,
  useRemoveTeamMember,
  useCreateUserTeam,
} from "@/lib/hooks/use-api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";

export function TeamSection() {
  const { session } = useAuth();
  const { data: teamData } = useUserTeam();
  const team = teamData?.team;
  const { data: membersData } = useTeamMembers(team?.id);
  const { data: watchlistData } = useTeamWatchlists(team?.id);
  const invite = useInviteTeamMember();
  const remove = useRemoveTeamMember();
  const createTeam = useCreateUserTeam();
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [teamName, setTeamName] = useState("");

  if (!session) return null;

  // No team — show "Create a Team" if user has extra seats
  if (!team) {
    if ((session.extra_seats ?? 0) <= 0) return null;
    return (
      <div className="space-y-2">
        <p className="text-xs font-medium uppercase text-muted-foreground">
          Create a Team
        </p>
        <p className="text-xs text-muted-foreground">
          You have {session.extra_seats} extra seats available
        </p>
        <Input
          placeholder="Team name"
          value={teamName}
          onChange={(e) => setTeamName(e.target.value)}
          className="h-7 text-xs"
        />
        <Button
          size="sm"
          className="w-full text-xs"
          disabled={!teamName.trim() || createTeam.isPending}
          onClick={() => {
            createTeam.mutate(
              {
                team_name: teamName.trim(),
                owner_username: session.username,
              },
              { onSuccess: () => setTeamName("") }
            );
          }}
        >
          Create Team
        </Button>
        {createTeam.isError && (
          <p className="text-xs text-destructive">
            {(createTeam.error as Error).message}
          </p>
        )}
      </div>
    );
  }

  const members = membersData?.members ?? [];
  const sharedBrands = watchlistData?.brands ?? [];
  const sharedTopics = watchlistData?.topics ?? [];
  const isOwner = team.role === "owner";

  return (
    <div className="space-y-2">
      <p className="text-xs font-medium uppercase text-muted-foreground">
        Team: {team.team_name}
      </p>
      {members.map((m) => (
        <div
          key={m.username}
          className="flex items-center justify-between text-sm"
        >
          <div className="flex items-center gap-1">
            <span>{m.username}</span>
            {m.role === "owner" && (
              <Badge variant="outline" className="px-1 py-0 text-[10px]">
                owner
              </Badge>
            )}
          </div>
          {m.role !== "owner" && isOwner && (
            <Button
              variant="ghost"
              size="sm"
              className="h-6 px-1 text-xs text-destructive"
              onClick={() =>
                remove.mutate({ teamId: team.id, username: m.username })
              }
            >
              Remove
            </Button>
          )}
        </div>
      ))}
      {isOwner && (
        <div className="space-y-1">
          <Input
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="h-7 text-xs"
          />
          <Input
            placeholder="Name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="h-7 text-xs"
          />
          <Button
            size="sm"
            className="w-full text-xs"
            disabled={!email.trim() || invite.isPending}
            onClick={() => {
              invite.mutate(
                {
                  teamId: team.id,
                  email: email.trim(),
                  name: name.trim(),
                },
                {
                  onSuccess: () => {
                    setEmail("");
                    setName("");
                  },
                }
              );
            }}
          >
            Invite Member
          </Button>
          {invite.isError && (
            <p className="text-xs text-destructive">
              {(invite.error as Error).message}
            </p>
          )}
        </div>
      )}
      {!isOwner && sharedBrands.length > 0 && (
        <div>
          <p className="text-xs text-muted-foreground">Shared brands:</p>
          {sharedBrands.map((b) => (
            <p key={b} className="pl-2 text-xs">
              - {b}
            </p>
          ))}
        </div>
      )}
      {!isOwner && sharedTopics.length > 0 && (
        <div>
          <p className="text-xs text-muted-foreground">Shared topics:</p>
          {sharedTopics.map((t) => (
            <p key={t.topic_name} className="pl-2 text-xs">
              - {t.topic_name}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}
