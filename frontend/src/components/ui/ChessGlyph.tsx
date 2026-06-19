type Piece = "knight" | "king" | "pawn" | "rook" | "bishop" | "queen";

interface ChessGlyphProps {
  piece?: Piece;
  className?: string;
  /** Unicode chess glyph used as a lightweight silhouette. */
  title?: string;
}

const GLYPHS: Record<Piece, string> = {
  king: "♚",
  queen: "♛",
  rook: "♜",
  bishop: "♝",
  knight: "♞",
  pawn: "♟",
};

/**
 * A decorative chess piece silhouette. Uses the solid Unicode glyph so it reads
 * as a clean silhouette at any size without bundling SVG assets.
 */
export function ChessGlyph({ piece = "knight", className = "", title }: ChessGlyphProps) {
  return (
    <span className={`select-none leading-none ${className}`} aria-hidden title={title}>
      {GLYPHS[piece]}
    </span>
  );
}
