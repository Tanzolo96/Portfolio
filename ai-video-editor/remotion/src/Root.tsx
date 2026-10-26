import {Composition} from 'remotion';
import {Edit, EditProps} from './Edit';

const fallback: EditProps = {
  video: 'cut.mp4',
  width: 1080,
  height: 1920,
  fps: 30,
  durationInFrames: 90,
  captions: [],
  hook: null,
  music: null,
  zooms: [],
  style: {},
};

export const Root: React.FC = () => (
  <Composition
    id="Edit"
    component={Edit}
    defaultProps={fallback}
    width={1080}
    height={1920}
    fps={30}
    durationInFrames={90}
    // edit.json (written by tools/plan.py) is passed via --props and sets the real size/length
    calculateMetadata={({props}) => ({
      width: props.width,
      height: props.height,
      fps: props.fps,
      durationInFrames: props.durationInFrames,
    })}
  />
);
