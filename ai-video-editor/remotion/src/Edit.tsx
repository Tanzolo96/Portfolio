import {
  AbsoluteFill,
  Audio,
  OffthreadVideo,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import {loadFont} from '@remotion/fonts';

// Bundled locally (public/fonts) so renders work offline. Add .woff2/.ttf files there and list them here.
const FONTS: Record<string, {file: string; weight: string}> = {
  Inter: {file: 'Inter-SemiBold.woff2', weight: '600'},
  'Inter ExtraBold': {file: 'Inter-ExtraBold.woff2', weight: '800'},
  Anton: {file: 'Anton-Regular.woff2', weight: '400'},
  Montserrat: {file: 'Montserrat-Black.woff2', weight: '900'},
};
for (const [family, f] of Object.entries(FONTS)) {
  loadFont({family, url: staticFile(`fonts/${f.file}`), weight: f.weight});
}

type Word = {text: string; start: number; end: number};
type Caption = {start: number; end: number; words: Word[]; emphasis?: boolean};
type Zoom = {start: number; end: number; scale: number};

export type EditStyle = {
  captionFont?: string;
  captionFontSize?: number;
  captionColor?: string;
  captionHighlight?: string | null; // colour for the word being spoken; null = no karaoke highlight
  captionStroke?: string | null;
  captionY?: number; // 0 = top, 1 = bottom (centre of caption)
  captionUppercase?: boolean;
  captionLetterSpacing?: string;
  emphasisFont?: string;
  emphasisFontSize?: number;
  emphasisColor?: string;
  emphasisStroke?: string | null;
  hookFont?: string;
  hookFontSize?: number;
  hookColor?: string;
  hookBackground?: string | null; // null = text straight on the video
  hookUppercase?: boolean;
  hookY?: number;
};

export type EditProps = {
  video: string;
  width: number;
  height: number;
  fps: number;
  durationInFrames: number;
  captions: Caption[];
  hook: {text: string; duration: number} | null;
  music: {src: string; volume: number} | null;
  zooms: Zoom[];
  style: EditStyle;
};

const zoomAt = (t: number, zooms: Zoom[], fps: number) => {
  for (const z of zooms) {
    if (t >= z.start && t < z.end) {
      // quick punch-in, eased over 4 frames
      const ramp = Math.min(1, ((t - z.start) * fps) / 4);
      return 1 + (z.scale - 1) * ramp;
    }
  }
  return 1;
};

const outline = (color: string | null | undefined, px: number) =>
  color ? {WebkitTextStroke: `${px}px ${color}`, paintOrder: 'stroke fill' as const} : {};

const Captions: React.FC<{captions: Caption[]; style: EditStyle; hookUntil: number}> = ({captions, style, hookUntil}) => {
  const frame = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  const t = frame / fps;
  const cap = captions.find((c) => t >= c.start && t < c.end);
  if (!cap || t < hookUntil) return null;

  const k = width / 1080; // sizes in style.json are for a 1080-wide frame
  const pop = spring({frame: frame - Math.round(cap.start * fps), fps, config: {damping: 14, stiffness: 220}, durationInFrames: 6});
  const emph = cap.emphasis;
  const size = (emph ? style.emphasisFontSize ?? 120 : style.captionFontSize ?? 60) * k;
  const font = emph ? style.emphasisFont ?? 'Inter ExtraBold' : style.captionFont ?? 'Inter';
  return (
    <AbsoluteFill style={{pointerEvents: 'none'}}>
      <div
        style={{
          position: 'absolute',
          top: height * (style.captionY ?? 0.5),
          left: '7%',
          right: '7%',
          transform: `translateY(-50%) scale(${interpolate(pop, [0, 1], [emph ? 0.7 : 0.92, 1])})`,
          textAlign: 'center',
          fontFamily: font,
          fontWeight: FONTS[font]?.weight ?? 700,
          fontSize: size,
          lineHeight: 1.1,
          letterSpacing: emph ? '-0.02em' : style.captionLetterSpacing ?? '-0.04em',
          textTransform: emph || style.captionUppercase ? 'uppercase' : 'none',
          textShadow: emph ? 'none' : '0 2px 10px rgba(0,0,0,0.35)',
          ...(emph ? outline(style.emphasisStroke === undefined ? '#FFFFFF' : style.emphasisStroke, size / 14)
            : outline(style.captionStroke, size / 9)),
        }}
      >
        {cap.words.map((w, i) => {
          const active = t >= w.start && t < w.end;
          const color = emph
            ? style.emphasisColor ?? '#E3122B'
            : active && style.captionHighlight ? style.captionHighlight : style.captionColor ?? '#FFFFFF';
          return (
            <span key={i} style={{color}}>
              {w.text}
              {i < cap.words.length - 1 ? ' ' : ''}
            </span>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

const Hook: React.FC<{text: string; duration: number; style: EditStyle}> = ({text, duration, style}) => {
  const frame = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  const total = Math.round(duration * fps);
  if (frame >= total) return null;
  const k = width / 1080;
  const font = style.hookFont ?? 'Anton';
  const words = text.split(/\s+/);
  const out = interpolate(frame, [total - 5, total], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const boxed = Boolean(style.hookBackground);
  return (
    <AbsoluteFill style={{alignItems: 'center'}}>
      <div
        style={{
          position: 'absolute',
          top: height * (style.hookY ?? 0.14),
          maxWidth: '80%',
          padding: boxed ? '22px 34px' : 0,
          borderRadius: 18,
          background: style.hookBackground ?? 'transparent',
          color: style.hookColor ?? '#E3122B',
          fontFamily: font,
          fontWeight: FONTS[font]?.weight ?? 700,
          fontSize: (style.hookFontSize ?? 150) * k,
          lineHeight: 0.95,
          textAlign: 'center',
          textTransform: style.hookUppercase ?? true ? 'uppercase' : 'none',
          opacity: out,
          textShadow: boxed ? 'none' : '0 4px 24px rgba(0,0,0,0.3)',
        }}
      >
        {/* words land one after another, ~3 frames apart */}
        {words.map((w, i) => {
          const p = spring({frame: frame - i * 3, fps, config: {damping: 13, stiffness: 200}, durationInFrames: 8});
          return (
            <span key={i} style={{display: 'inline-block', opacity: p, transform: `translateY(${interpolate(p, [0, 1], [30, 0])}px)`}}>
              {w}
              {i < words.length - 1 ? ' ' : ''}
            </span>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

export const Edit: React.FC<EditProps> = ({video, captions, hook, music, zooms, style}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const scale = zoomAt(frame / fps, zooms, fps);
  return (
    <AbsoluteFill style={{backgroundColor: 'black'}}>
      <AbsoluteFill style={{transform: `scale(${scale})`}}>
        <OffthreadVideo src={staticFile(video)} style={{width: '100%', height: '100%', objectFit: 'cover'}} />
      </AbsoluteFill>
      {music ? <Audio src={staticFile(music.src)} volume={music.volume} loop /> : null}
      <Captions captions={captions} style={style} hookUntil={hook ? hook.duration : 0} />
      {hook ? <Hook text={hook.text} duration={hook.duration} style={style} /> : null}
    </AbsoluteFill>
  );
};
