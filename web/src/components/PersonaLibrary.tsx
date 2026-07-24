import { useCallback, useEffect, useRef, useState } from "react";
import {
  IconDownload,
  IconExternalLink,
  IconTrash,
  IconUpload,
} from "@tabler/icons-react";
import type { PersonaRead } from "../api";
import {
  deletePersona,
  fetchPersonas,
  importPersona,
  importPersonaZip,
} from "../api/personas";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Label } from "./ui/label";

export function PersonaLibrary({ token }: { token: string }) {
  const [items, setItems] = useState<PersonaRead[]>([]);
  const [sourceUrl, setSourceUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const zipInputRef = useRef<HTMLInputElement>(null);

  const refresh = useCallback(async () => {
    try {
      setItems(await fetchPersonas(token));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [token]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const install = async () => {
    if (!sourceUrl.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const installed = await importPersona(token, sourceUrl.trim());
      setItems((current) => [...current, installed]);
      setSourceUrl("");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  const uploadZip = async (file: File) => {
    setUploading(true);
    setError(null);
    try {
      const installed = await importPersonaZip(token, file);
      setItems((current) => [...current, installed]);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setUploading(false);
    }
  };

  const remove = async (persona: PersonaRead) => {
    if (!window.confirm(`Delete persona "${persona.name}" from the library?`)) return;
    setError(null);
    try {
      await deletePersona(token, persona.id);
      setItems((current) => current.filter((item) => item.id !== persona.id));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  return (
    <div className="persona-library space-y-4">
      <div className="space-y-1.5">
        <Label htmlFor="persona-source">GitHub repository</Label>
        <div className="flex gap-2">
          <Input
            id="persona-source"
            value={sourceUrl}
            onChange={(event) => setSourceUrl(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") install();
            }}
            placeholder="https://github.com/owner/persona-skill"
            disabled={loading || uploading}
          />
          <Button
            onClick={install}
            disabled={loading || uploading || !sourceUrl.trim()}
          >
            <IconDownload size={16} />
            {loading ? "Installing" : "Install"}
          </Button>
        </div>
        <p className="text-xs leading-relaxed text-muted-foreground">
          The complete repository is pinned to its current commit. SKILL.md becomes
          the core persona; references and examples remain available on demand.
        </p>
      </div>

      <div className="space-y-1.5">
        <Label>Local package</Label>
        <input
          ref={zipInputRef}
          type="file"
          accept=".zip,application/zip,application/x-zip-compressed"
          hidden
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) void uploadZip(file);
            event.target.value = "";
          }}
        />
        <Button
          type="button"
          variant="outline"
          onClick={() => zipInputRef.current?.click()}
          disabled={loading || uploading}
        >
          <IconUpload size={16} />
          {uploading ? "Uploading" : "Upload ZIP"}
        </Button>
        <p className="text-xs leading-relaxed text-muted-foreground">
          Upload a downloaded skill repository up to 25 MB. A root folder in the
          ZIP is handled automatically.
        </p>
      </div>

      {error && <div className="text-xs text-destructive">{error}</div>}

      <div className="flex flex-col gap-2">
        {items.length === 0 && (
          <div className="border-t border-border py-4 text-sm text-muted-foreground">
            No personas installed.
          </div>
        )}
        {items.map((persona) => (
          <div
            key={persona.id}
            className="persona-library-item flex items-start gap-3 border-t border-border py-3"
          >
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <span className="truncate text-sm font-medium text-foreground">
                  {persona.name}
                </span>
                {persona.license && (
                  <span className="text-[10px] uppercase text-muted-foreground">
                    {persona.license}
                  </span>
                )}
              </div>
              <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-muted-foreground">
                {persona.description || "No description provided."}
              </p>
              <div className="mt-1.5 flex items-center gap-3 text-[11px] text-muted-foreground">
                <span>{persona.resources.length} resources</span>
                <span>{persona.assigned_agent_count} agents</span>
                {persona.source_url.startsWith("https://") ? (
                  <a
                    href={persona.source_url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 hover:text-foreground"
                  >
                    Source <IconExternalLink size={12} />
                  </a>
                ) : (
                  <span>Local ZIP</span>
                )}
              </div>
            </div>
            <button
              type="button"
              className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-muted-foreground hover:bg-destructive/10 hover:text-destructive disabled:cursor-not-allowed disabled:opacity-40"
              onClick={() => remove(persona)}
              disabled={persona.assigned_agent_count > 0}
              title={
                persona.assigned_agent_count > 0
                  ? "Remove this persona from agents before deleting it"
                  : "Delete persona"
              }
            >
              <IconTrash size={16} />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
