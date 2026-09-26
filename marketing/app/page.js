import Motion from '../components/Motion';
import {
  Comparison, Compete, Cta, Hero, NotJustALog, ProgressDraws, RankUp, Rival,
  TheMoment, TrainingIdentity,
} from '../components/Sections';

export default function Page() {
  return (
    <main>
      <Motion />
      <Hero />
      <NotJustALog />
      <TheMoment />
      <TrainingIdentity />
      <RankUp />
      <ProgressDraws />
      <Compete />
      <Rival />
      <Comparison />
      <Cta />
    </main>
  );
}
