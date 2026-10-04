import {api} from './api.js';

export const dashboardService={
  overview(tariff){
    const value=Number(tariff)||8.5;
    return api.get('/dashboard/overview?tariff='+encodeURIComponent(value));
  },
};
