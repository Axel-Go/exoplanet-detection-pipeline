# exoplanet-detection-pipeline

When a planet passes in front of its star, the star dims a little. It does that every time it comes round, so you get a repeating dip in the star's brightness and that dip is enough to figure out that the planet is there, how long its year is, and how big it is. This searches NASA's TESS data for those dips.

It also checks itself. Half the stars it looks at have planets that are already confirmed, and it isn't told which ones. So when a run finishes I can compare what it found against the real answers and say how often it gets it right, and how often it doesn't. Without that it would just be printing numbers I cant back up.



