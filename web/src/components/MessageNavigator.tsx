import type { MessageMarker } from "../lib/messageNavigation";

interface MessageNavigatorProps {
  markers: MessageMarker[];
  totalItems: number;
  activeIndex?: number | null;
  onNavigate: (index: number) => void;
}

function markerPosition(index: number, totalItems: number): number {
  if (totalItems <= 1) return 50;
  return 3 + (index / (totalItems - 1)) * 94;
}

export function MessageNavigator({
  markers,
  totalItems,
  activeIndex,
  onNavigate,
}: MessageNavigatorProps) {
  if (markers.length < 2) return null;

  return (
    <nav className="message-navigator" aria-label="Your message shortcuts">
      <span className="message-navigator-track" aria-hidden="true" />
      {markers.map((marker, ordinal) => {
        const isActive = marker.index === activeIndex;
        const label = `Jump to your message ${ordinal + 1}: ${marker.preview}`;
        return (
          <button
            key={marker.index}
            type="button"
            className={`message-navigator-marker${isActive ? " is-active" : ""}`}
            style={{ top: `${markerPosition(marker.index, totalItems)}%` }}
            onClick={() => onNavigate(marker.index)}
            aria-label={label}
            aria-current={isActive ? "location" : undefined}
          >
            <span className="message-navigator-tooltip" aria-hidden="true">
              <span className="message-navigator-number">{ordinal + 1}</span>
              <span className="message-navigator-preview">{marker.preview}</span>
            </span>
          </button>
        );
      })}
    </nav>
  );
}
